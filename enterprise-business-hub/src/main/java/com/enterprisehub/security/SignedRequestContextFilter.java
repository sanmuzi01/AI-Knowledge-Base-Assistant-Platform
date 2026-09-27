package com.enterprisehub.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;

/**
 * 策略执行点（PEP）：每个业务请求都要带 FastAPI 签发的短时效 RequestContext，
 * 验证签名 + 有效期 + 防重放后才放行——权限判断本身在 FastAPI 一侧，这里只验证
 * "这份上下文是不是 FastAPI 真的签发的、有没有过期、有没有被重放"。
 *
 * `/actuator/**` 是健康检查，不带业务语义，放行不验证——跟主项目 `/health` 公开
 * 探活是同一个道理。
 */
@Component
public class SignedRequestContextFilter extends OncePerRequestFilter {

    public static final String CONTEXT_HEADER = "X-Context";
    public static final String SIGNATURE_HEADER = "X-Signature";

    private final HmacSignatureVerifier verifier;
    private final NonceStore nonceStore;
    private final ObjectMapper objectMapper;
    private final long maxClockSkewSeconds;

    public SignedRequestContextFilter(
            HmacSignatureVerifier verifier,
            NonceStore nonceStore,
            ObjectMapper objectMapper,
            @Value("${enterprise-hub.security.max-clock-skew-seconds:300}") long maxClockSkewSeconds
    ) {
        this.verifier = verifier;
        this.nonceStore = nonceStore;
        this.objectMapper = objectMapper;
        this.maxClockSkewSeconds = maxClockSkewSeconds;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return request.getRequestURI().startsWith("/actuator/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String contextB64 = request.getHeader(CONTEXT_HEADER);
        String signature = request.getHeader(SIGNATURE_HEADER);

        if (contextB64 == null || signature == null) {
            reject(response, HttpServletResponse.SC_BAD_REQUEST, "缺少 " + CONTEXT_HEADER + "/" + SIGNATURE_HEADER);
            return;
        }
        if (!verifier.verify(contextB64, signature)) {
            reject(response, HttpServletResponse.SC_UNAUTHORIZED, "签名校验失败");
            return;
        }

        RequestContext context;
        try {
            byte[] decoded = Base64.getDecoder().decode(contextB64);
            context = objectMapper.readValue(new String(decoded, StandardCharsets.UTF_8), RequestContext.class);
        } catch (Exception e) {
            reject(response, HttpServletResponse.SC_BAD_REQUEST, "RequestContext 格式不对");
            return;
        }

        long now = Instant.now().getEpochSecond();
        if (Math.abs(now - context.timestamp()) > maxClockSkewSeconds) {
            reject(response, HttpServletResponse.SC_UNAUTHORIZED, "RequestContext 已过期或时间戳不合理");
            return;
        }
        if (context.nonce() == null || context.nonce().isBlank()
                || !nonceStore.rememberIfNew(context.nonce(), maxClockSkewSeconds)) {
            reject(response, HttpServletResponse.SC_UNAUTHORIZED, "重复的请求（nonce 已被使用）");
            return;
        }

        RequestContextHolder.set(context);
        try {
            chain.doFilter(request, response);
        } finally {
            RequestContextHolder.clear();
        }
    }

    private void reject(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"detail\":\"" + message.replace("\"", "'") + "\"}");
    }
}
