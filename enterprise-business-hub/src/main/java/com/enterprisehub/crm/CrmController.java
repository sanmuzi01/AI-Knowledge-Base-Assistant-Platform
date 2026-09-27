package com.enterprisehub.crm;

import com.enterprisehub.crm.dto.CreateFollowUpRequest;
import com.enterprisehub.crm.dto.UpsertOpportunityRequest;
import com.enterprisehub.idempotency.IdempotencyService;
import com.enterprisehub.security.RequestContext;
import com.enterprisehub.security.RequestContextHolder;
import com.enterprisehub.security.ScopeGuard;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** CRM 客户跟进闭环的 REST 接口，供 FastAPI 侧的销售 Agent 工具调用
 * （service/tools/crm.py，跟 oa_leave.py/procurement.py 是同一种薄工具层）。 */
@RestController
@RequestMapping("/crm")
public class CrmController {
    public static final String IDEMPOTENCY_HEADER = "Idempotency-Key";

    private final CrmService crmService;
    private final IdempotencyService idempotencyService;

    public CrmController(CrmService crmService, IdempotencyService idempotencyService) {
        this.crmService = crmService;
        this.idempotencyService = idempotencyService;
    }

    @GetMapping("/customers/{id}")
    public Object getCustomerSummary(@PathVariable("id") long id) {
        ScopeGuard.require("crm.read");
        return crmService.getCustomerSummary(id, requireTeamId());
    }

    @PostMapping("/customers/{id}/followups")
    public ResponseEntity<Object> createFollowUpDraft(
            @PathVariable("id") long id, @Valid @RequestBody CreateFollowUpRequest body,
            @RequestHeader(value = IDEMPOTENCY_HEADER, required = false) String idempotencyKey) {
        ScopeGuard.require("crm.write");
        RequestContext ctx = RequestContextHolder.current();
        long teamId = requireTeamId();
        return idempotencyService.execute(idempotencyKey, () -> {
            var dto = crmService.createFollowUpDraft(id, teamId, ctx.userId(), body.content(), ctx.traceId());
            return ResponseEntity.<Object>ok(dto);
        });
    }

    @PostMapping("/followups/{id}/confirm")
    public ResponseEntity<Object> confirmFollowUp(
            @PathVariable("id") long id,
            @RequestHeader(value = IDEMPOTENCY_HEADER, required = false) String idempotencyKey) {
        ScopeGuard.require("crm.write");
        RequestContext ctx = RequestContextHolder.current();
        return idempotencyService.execute(idempotencyKey, () -> {
            var dto = crmService.confirmFollowUp(id, ctx.userId(), ctx.traceId());
            return ResponseEntity.<Object>ok(dto);
        });
    }

    @PostMapping("/customers/{id}/opportunities")
    public ResponseEntity<Object> upsertOpportunity(
            @PathVariable("id") long id, @Valid @RequestBody UpsertOpportunityRequest body,
            @RequestHeader(value = IDEMPOTENCY_HEADER, required = false) String idempotencyKey) {
        ScopeGuard.require("crm.write");
        RequestContext ctx = RequestContextHolder.current();
        long teamId = requireTeamId();
        return idempotencyService.execute(idempotencyKey, () -> {
            var dto = crmService.upsertOpportunity(id, teamId, ctx.userId(), body, ctx.traceId());
            return ResponseEntity.<Object>ok(dto);
        });
    }

    @GetMapping("/customers/{id}/opportunities")
    public Object listOpportunities(@PathVariable("id") long id) {
        ScopeGuard.require("crm.read");
        return crmService.listOpportunities(id, requireTeamId());
    }

    private long requireTeamId() {
        RequestContext ctx = RequestContextHolder.current();
        if (ctx.teamId() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "CRM 操作需要部门上下文（team_id）");
        }
        return ctx.teamId();
    }
}
