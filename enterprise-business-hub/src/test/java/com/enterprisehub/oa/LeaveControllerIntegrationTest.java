package com.enterprisehub.oa;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * OA 请假闭环的真实 HTTP 集成测试：走完整的 SignedRequestContextFilter →
 * Controller → Service → 真实 MySQL 全链路，不是单测 mock。
 *
 * 跟主项目 Python 测试同一个思路：不建独立测试库，复用 enterprise_business，
 * 每个用户 ID 随机生成避免相互冲突，测试结束自己清理建的数据。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class LeaveControllerIntegrationTest {

    private static final String HMAC_SECRET = "test-secret-not-for-production";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private long userId;
    private long approverId;
    private long teamId;

    @BeforeEach
    void setUp() {
        // 每个测试方法用一段不会撞到别的测试/别的 worker 的用户 ID 区间。
        userId = ThreadLocalRandom.current().nextLong(9_000_000L, 9_999_000L);
        approverId = userId + 1;
        teamId = 2L;
        jdbc.update("INSERT INTO leave_balance (user_id, leave_type_id, year, remaining_days) VALUES (?, 1, ?, 10)",
                userId, Instant.now().atZone(java.time.ZoneOffset.UTC).getYear());
    }

    @AfterEach
    void tearDown() {
        jdbc.update("DELETE FROM leave_request WHERE applicant_user_id = ?", userId);
        jdbc.update("DELETE FROM leave_balance WHERE user_id = ?", userId);
        jdbc.update("DELETE FROM audit_event WHERE user_id IN (?, ?)", userId, approverId);
    }

    private HttpHeaders signedHeaders(long uid, List<String> scopes, String operation) {
        try {
            Map<String, Object> context = Map.of(
                    "user_id", uid,
                    "team_id", teamId,
                    "scopes", scopes,
                    "operation", operation,
                    "trace_id", UUID.randomUUID().toString(),
                    "timestamp", Instant.now().getEpochSecond(),
                    "nonce", UUID.randomUUID().toString().replace("-", "")
            );
            String json = MAPPER.writeValueAsString(context);
            String contextB64 = Base64.getEncoder().encodeToString(json.getBytes(StandardCharsets.UTF_8));

            javax.crypto.Mac mac = javax.crypto.Mac.getInstance("HmacSHA256");
            mac.init(new javax.crypto.spec.SecretKeySpec(HMAC_SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] sig = mac.doFinal(contextB64.getBytes(StandardCharsets.UTF_8));
            String sigHex = java.util.HexFormat.of().formatHex(sig);

            HttpHeaders headers = new HttpHeaders();
            headers.set("X-Context", contextB64);
            headers.set("X-Signature", sigHex);
            headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
            return headers;
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    private String url(String path) {
        return "http://127.0.0.1:" + port + path;
    }

    @Test
    void fullHappyPath_balanceCheck_draft_submit_approve_deductsBalance() {
        HttpHeaders readHeaders = signedHeaders(userId, List.of("oa.leave.read"), "get_leave_balance");
        ResponseEntity<Map[]> balanceResp = rest.exchange(url("/oa/leave/balance"), HttpMethod.GET,
                new HttpEntity<>(readHeaders), Map[].class);
        assertThat(balanceResp.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(balanceResp.getBody()[0].get("remainingDays")).isEqualTo(10.0);

        HttpHeaders writeHeaders = signedHeaders(userId, List.of("oa.leave.write"), "create_leave_draft");
        writeHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        Map<String, Object> draftBody = Map.of(
                "leaveTypeCode", "annual", "startDate", "2026-11-01", "endDate", "2026-11-02", "reason", "集成测试"
        );
        ResponseEntity<Map> draftResp = rest.exchange(url("/oa/leave/requests"), HttpMethod.POST,
                new HttpEntity<>(draftBody, writeHeaders), Map.class);
        assertThat(draftResp.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(draftResp.getBody().get("status")).isEqualTo("DRAFT");
        long requestId = ((Number) draftResp.getBody().get("id")).longValue();

        HttpHeaders submitHeaders = signedHeaders(userId, List.of("oa.leave.write"), "submit_leave_request");
        submitHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<Map> submitResp = rest.exchange(url("/oa/leave/requests/" + requestId + "/submit"),
                HttpMethod.POST, new HttpEntity<>(submitHeaders), Map.class);
        assertThat(submitResp.getBody().get("status")).isEqualTo("SUBMITTED");

        HttpHeaders approveHeaders = signedHeaders(approverId, List.of("oa.leave.approve"), "approve_leave_request");
        approveHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<Map> approveResp = rest.exchange(url("/oa/leave/requests/" + requestId + "/approve"),
                HttpMethod.POST, new HttpEntity<>(Map.of("note", "同意"), approveHeaders), Map.class);
        assertThat(approveResp.getBody().get("status")).isEqualTo("APPROVED");

        ResponseEntity<Map[]> afterBalance = rest.exchange(url("/oa/leave/balance"), HttpMethod.GET,
                new HttpEntity<>(signedHeaders(userId, List.of("oa.leave.read"), "get_leave_balance")), Map[].class);
        assertThat(afterBalance.getBody()[0].get("remainingDays")).isEqualTo(8.0);
    }

    @Test
    void missingScope_returns403() {
        HttpHeaders headers = signedHeaders(userId, List.of("some.other.scope"), "get_leave_balance");
        ResponseEntity<String> resp = rest.exchange(url("/oa/leave/balance"), HttpMethod.GET,
                new HttpEntity<>(headers), String.class);
        assertThat(resp.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void badSignature_returns401() {
        HttpHeaders headers = signedHeaders(userId, List.of("oa.leave.read"), "get_leave_balance");
        headers.set("X-Signature", "0".repeat(64));
        ResponseEntity<String> resp = rest.exchange(url("/oa/leave/balance"), HttpMethod.GET,
                new HttpEntity<>(headers), String.class);
        assertThat(resp.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void insufficientBalance_submitFails() {
        HttpHeaders writeHeaders = signedHeaders(userId, List.of("oa.leave.write"), "create_leave_draft");
        writeHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        // 11 天的年假请求，但账上只有 10 天。
        Map<String, Object> draftBody = Map.of(
                "leaveTypeCode", "annual", "startDate", "2026-11-01", "endDate", "2026-11-11", "reason", "超额测试"
        );
        ResponseEntity<Map> draftResp = rest.exchange(url("/oa/leave/requests"), HttpMethod.POST,
                new HttpEntity<>(draftBody, writeHeaders), Map.class);
        long requestId = ((Number) draftResp.getBody().get("id")).longValue();

        HttpHeaders submitHeaders = signedHeaders(userId, List.of("oa.leave.write"), "submit_leave_request");
        submitHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<String> submitResp = rest.exchange(url("/oa/leave/requests/" + requestId + "/submit"),
                HttpMethod.POST, new HttpEntity<>(submitHeaders), String.class);
        assertThat(submitResp.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void replayingIdempotencyKey_doesNotCreateSecondDraft() {
        HttpHeaders writeHeaders = signedHeaders(userId, List.of("oa.leave.write"), "create_leave_draft");
        String key = UUID.randomUUID().toString();
        writeHeaders.set("Idempotency-Key", key);
        Map<String, Object> draftBody = Map.of(
                "leaveTypeCode", "annual", "startDate", "2026-11-01", "endDate", "2026-11-02", "reason", "幂等测试"
        );

        ResponseEntity<Map> first = rest.exchange(url("/oa/leave/requests"), HttpMethod.POST,
                new HttpEntity<>(draftBody, writeHeaders), Map.class);
        // 第二次用完全一样的 Idempotency-Key（context/签名/nonce 都重新生成，只有这个 key 复用）。
        HttpHeaders writeHeaders2 = signedHeaders(userId, List.of("oa.leave.write"), "create_leave_draft");
        writeHeaders2.set("Idempotency-Key", key);
        ResponseEntity<Map> second = rest.exchange(url("/oa/leave/requests"), HttpMethod.POST,
                new HttpEntity<>(draftBody, writeHeaders2), Map.class);

        assertThat(second.getBody().get("id")).isEqualTo(first.getBody().get("id"));

        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM leave_request WHERE applicant_user_id = ?", Integer.class, userId);
        assertThat(count).isEqualTo(1);
    }

    @Test
    void rejectedRequest_doesNotDeductBalance() {
        HttpHeaders writeHeaders = signedHeaders(userId, List.of("oa.leave.write"), "create_leave_draft");
        writeHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        Map<String, Object> draftBody = Map.of(
                "leaveTypeCode", "annual", "startDate", "2026-11-01", "endDate", "2026-11-02", "reason", "拒绝测试"
        );
        ResponseEntity<Map> draftResp = rest.exchange(url("/oa/leave/requests"), HttpMethod.POST,
                new HttpEntity<>(draftBody, writeHeaders), Map.class);
        long requestId = ((Number) draftResp.getBody().get("id")).longValue();

        HttpHeaders submitHeaders = signedHeaders(userId, List.of("oa.leave.write"), "submit_leave_request");
        submitHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        rest.exchange(url("/oa/leave/requests/" + requestId + "/submit"), HttpMethod.POST,
                new HttpEntity<>(submitHeaders), Map.class);

        HttpHeaders rejectHeaders = signedHeaders(approverId, List.of("oa.leave.approve"), "reject_leave_request");
        rejectHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<Map> rejectResp = rest.exchange(url("/oa/leave/requests/" + requestId + "/reject"),
                HttpMethod.POST, new HttpEntity<>(Map.of("note", "人手不够"), rejectHeaders), Map.class);
        assertThat(rejectResp.getBody().get("status")).isEqualTo("REJECTED");

        ResponseEntity<Map[]> afterBalance = rest.exchange(url("/oa/leave/balance"), HttpMethod.GET,
                new HttpEntity<>(signedHeaders(userId, List.of("oa.leave.read"), "get_leave_balance")), Map[].class);
        assertThat(afterBalance.getBody()[0].get("remainingDays")).isEqualTo(10.0);
    }
}
