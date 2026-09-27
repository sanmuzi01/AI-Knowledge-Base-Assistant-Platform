package com.enterprisehub.crm;

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

/** CRM 闭环的真实 HTTP 集成测试，跟 Leave/Procurement 是同一套骨架。 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class CrmControllerIntegrationTest {

    private static final String HMAC_SECRET = "test-secret-not-for-production";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    private long userId;
    private long teamId;
    private long customerId;
    private long otherTeamCustomerId;

    @BeforeEach
    void setUp() {
        userId = ThreadLocalRandom.current().nextLong(7_000_000L, 7_999_000L);
        teamId = userId;

        jdbc.update("INSERT INTO customer (name, industry, owner_user_id, team_id, created_at) "
                + "VALUES (?, '制造业', ?, ?, NOW())", "测试客户-" + userId, userId, teamId);
        customerId = jdbc.queryForObject("SELECT id FROM customer WHERE team_id=? ORDER BY id DESC LIMIT 1",
                Long.class, teamId);
        jdbc.update("INSERT INTO contact (customer_id, name, title, phone, email) VALUES (?, ?, ?, ?, ?)",
                customerId, "张经理", "采购总监", "13800000000", "zhang@example.com");

        jdbc.update("INSERT INTO customer (name, industry, owner_user_id, team_id, created_at) "
                + "VALUES (?, '零售业', ?, ?, NOW())", "别的部门客户-" + userId, userId, teamId + 1);
        otherTeamCustomerId = jdbc.queryForObject(
                "SELECT id FROM customer WHERE team_id=? ORDER BY id DESC LIMIT 1", Long.class, teamId + 1);
    }

    @AfterEach
    void tearDown() {
        jdbc.update("DELETE FROM opportunity WHERE customer_id IN (?, ?)", customerId, otherTeamCustomerId);
        jdbc.update("DELETE FROM follow_up WHERE customer_id IN (?, ?)", customerId, otherTeamCustomerId);
        jdbc.update("DELETE FROM contact WHERE customer_id IN (?, ?)", customerId, otherTeamCustomerId);
        jdbc.update("DELETE FROM customer WHERE id IN (?, ?)", customerId, otherTeamCustomerId);
        jdbc.update("DELETE FROM audit_event WHERE user_id = ?", userId);
    }

    private HttpHeaders signedHeaders(long uid, Long teamIdForContext, List<String> scopes, String operation) {
        try {
            Map<String, Object> context = Map.of(
                    "user_id", uid, "team_id", teamIdForContext, "scopes", scopes, "operation", operation,
                    "trace_id", UUID.randomUUID().toString(), "timestamp", Instant.now().getEpochSecond(),
                    "nonce", UUID.randomUUID().toString().replace("-", "")
            );
            String json = MAPPER.writeValueAsString(context);
            String contextB64 = Base64.getEncoder().encodeToString(json.getBytes(StandardCharsets.UTF_8));
            javax.crypto.Mac mac = javax.crypto.Mac.getInstance("HmacSHA256");
            mac.init(new javax.crypto.spec.SecretKeySpec(HMAC_SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            String sigHex = java.util.HexFormat.of().formatHex(
                    mac.doFinal(contextB64.getBytes(StandardCharsets.UTF_8)));
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
    void fullHappyPath_summary_followup_confirm_opportunity() {
        ResponseEntity<Map> summary = rest.exchange(url("/crm/customers/" + customerId), HttpMethod.GET,
                new HttpEntity<>(signedHeaders(userId, teamId, List.of("crm.read"), "get_customer_summary")), Map.class);
        assertThat(summary.getStatusCode()).isEqualTo(HttpStatus.OK);
        List<?> contacts = (List<?>) summary.getBody().get("contacts");
        assertThat(contacts).hasSize(1);

        HttpHeaders writeHeaders = signedHeaders(userId, teamId, List.of("crm.write"), "create_followup_draft");
        writeHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<Map> draft = rest.exchange(url("/crm/customers/" + customerId + "/followups"),
                HttpMethod.POST, new HttpEntity<>(Map.of("content", "拜访了张经理，对方案感兴趣"), writeHeaders), Map.class);
        assertThat(draft.getBody().get("status")).isEqualTo("DRAFT");
        long followUpId = ((Number) draft.getBody().get("id")).longValue();

        HttpHeaders confirmHeaders = signedHeaders(userId, teamId, List.of("crm.write"), "submit_customer_followup");
        confirmHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<Map> confirmed = rest.exchange(url("/crm/followups/" + followUpId + "/confirm"),
                HttpMethod.POST, new HttpEntity<>(confirmHeaders), Map.class);
        assertThat(confirmed.getBody().get("status")).isEqualTo("CONFIRMED");

        HttpHeaders oppHeaders = signedHeaders(userId, teamId, List.of("crm.write"), "create_or_update_opportunity");
        oppHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<Map> created = rest.exchange(url("/crm/customers/" + customerId + "/opportunities"),
                HttpMethod.POST, new HttpEntity<>(Map.of("stage", "QUALIFIED", "amount", 50000), oppHeaders), Map.class);
        assertThat(created.getBody().get("stage")).isEqualTo("QUALIFIED");
        long opportunityId = ((Number) created.getBody().get("id")).longValue();

        HttpHeaders updateHeaders = signedHeaders(userId, teamId, List.of("crm.write"), "create_or_update_opportunity");
        updateHeaders.set("Idempotency-Key", UUID.randomUUID().toString());
        ResponseEntity<Map> updated = rest.exchange(url("/crm/customers/" + customerId + "/opportunities"),
                HttpMethod.POST,
                new HttpEntity<>(Map.of("opportunityId", opportunityId, "stage", "NEGOTIATION", "amount", 60000),
                        updateHeaders),
                Map.class);
        assertThat(updated.getBody().get("id")).isEqualTo((int) opportunityId);
        assertThat(updated.getBody().get("stage")).isEqualTo("NEGOTIATION");

        ResponseEntity<List> opportunities = rest.exchange(url("/crm/customers/" + customerId + "/opportunities"),
                HttpMethod.GET, new HttpEntity<>(signedHeaders(userId, teamId, List.of("crm.read"), "list")), List.class);
        assertThat(opportunities.getBody()).hasSize(1); // 更新了同一条，不是新建了一条
    }

    @Test
    void differentTeam_customerNotFound() {
        // customerId 属于 teamId，用 teamId+1 的上下文去查会被当成不存在（部门数据隔离）。
        ResponseEntity<String> resp = rest.exchange(url("/crm/customers/" + customerId), HttpMethod.GET,
                new HttpEntity<>(signedHeaders(userId, teamId + 1, List.of("crm.read"), "get_customer_summary")),
                String.class);
        assertThat(resp.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void missingScope_returns403() {
        ResponseEntity<String> resp = rest.exchange(url("/crm/customers/" + customerId), HttpMethod.GET,
                new HttpEntity<>(signedHeaders(userId, teamId, List.of("other.scope"), "get_customer_summary")),
                String.class);
        assertThat(resp.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void replayingIdempotencyKey_doesNotCreateSecondFollowUp() {
        HttpHeaders writeHeaders = signedHeaders(userId, teamId, List.of("crm.write"), "create_followup_draft");
        String key = UUID.randomUUID().toString();
        writeHeaders.set("Idempotency-Key", key);
        Map<String, Object> body = Map.of("content", "第一次跟进");

        ResponseEntity<Map> first = rest.exchange(url("/crm/customers/" + customerId + "/followups"),
                HttpMethod.POST, new HttpEntity<>(body, writeHeaders), Map.class);
        HttpHeaders writeHeaders2 = signedHeaders(userId, teamId, List.of("crm.write"), "create_followup_draft");
        writeHeaders2.set("Idempotency-Key", key);
        ResponseEntity<Map> second = rest.exchange(url("/crm/customers/" + customerId + "/followups"),
                HttpMethod.POST, new HttpEntity<>(body, writeHeaders2), Map.class);

        assertThat(second.getBody().get("id")).isEqualTo(first.getBody().get("id"));
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM follow_up WHERE customer_id = ?", Integer.class, customerId);
        assertThat(count).isEqualTo(1);
    }
}
