package com.enterprisehub.audit;

import org.springframework.stereotype.Service;

@Service
public class AuditService {
    private final AuditEventRepository repository;

    public AuditService(AuditEventRepository repository) {
        this.repository = repository;
    }

    public void record(long userId, String action, String resourceType, Long resourceId, String detail, String traceId) {
        repository.save(new AuditEvent(userId, action, resourceType, resourceId, detail, traceId));
    }
}
