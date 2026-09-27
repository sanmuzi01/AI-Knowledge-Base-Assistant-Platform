package com.enterprisehub.idempotency;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.util.function.Supplier;

@Service
public class IdempotencyService {
    private final IdempotencyRepository repository;
    private final ObjectMapper objectMapper;

    public IdempotencyService(IdempotencyRepository repository, ObjectMapper objectMapper) {
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    /**
     * 有这个 key 的记录就直接把当年存的结果原样返回，不重新跑 {@code action}；
     * 没有就跑一遍、把结果存起来再返回。
     *
     * 不加分布式锁：同一个 key 极短时间内并发打进来的话，两边都可能判定"没有记录"
     * 然后各自执行一次——留作已知的窄口径限制（跟主项目乐观锁字段"先加字段不接
     * 强制逻辑"是同一种务实取舍），真正需要严格并发互斥时再加数据库唯一约束
     * 抢占（`INSERT ... ON DUPLICATE KEY` 或先插入一行"processing"占位）。
     */
    @Transactional
    public ResponseEntity<Object> execute(String idempotencyKey, Supplier<ResponseEntity<Object>> action) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            return action.get();
        }
        Optional<IdempotencyRecord> existing = repository.findById(idempotencyKey);
        if (existing.isPresent()) {
            IdempotencyRecord record = existing.get();
            Object body = readBody(record.getResponseBody());
            return ResponseEntity.status(record.getStatusCode()).body(body);
        }

        ResponseEntity<Object> result = action.get();
        String bodyJson = writeBody(result.getBody());
        repository.save(new IdempotencyRecord(idempotencyKey, result.getStatusCode().value(), bodyJson));
        return result;
    }

    private Object readBody(String json) {
        try {
            return objectMapper.readValue(json, Object.class);
        } catch (Exception e) {
            return null;
        }
    }

    private String writeBody(Object body) {
        try {
            return objectMapper.writeValueAsString(body);
        } catch (Exception e) {
            return "null";
        }
    }
}
