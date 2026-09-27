package com.enterprisehub.security;

import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 防重放：记住见过的 nonce，有效期跟签名的时钟容差一致——过了容差窗口的 nonce
 * 反正也会被时间戳校验拒绝，不用无限期存。
 *
 * MVP 用进程内 Map；多实例部署时不同实例看不到彼此的 nonce，同一个 nonce 打到
 * 不同实例可能都放行——这是已知的简化，生产多实例要换成 Redis（同 Python 侧
 * 限流/防重放用 Redis 是同一个道理）。
 */
@Component
public class NonceStore {
    private final Map<String, Instant> seen = new ConcurrentHashMap<>();

    /** 第一次见过返回 true 并记住；见过就返回 false（重放）。 */
    public boolean rememberIfNew(String nonce, long ttlSeconds) {
        Instant now = Instant.now();
        Instant existing = seen.putIfAbsent(nonce, now);
        if (existing != null) {
            return false;
        }
        cleanup(now.minusSeconds(ttlSeconds * 4));
        return true;
    }

    private void cleanup(Instant olderThan) {
        seen.entrySet().removeIf(e -> e.getValue().isBefore(olderThan));
    }
}
