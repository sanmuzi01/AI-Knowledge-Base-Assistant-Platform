package com.enterprisehub.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

/** 对 `X-Context` 请求头（base64 编码的 JSON 原文，见 SignedRequestContextFilter）算 HMAC-SHA256，
 * 跟 `X-Signature` 头做常量时间比较——不逐字节比较普通字符串，避免时序侧信道。 */
@Component
public class HmacSignatureVerifier {
    private static final String ALGORITHM = "HmacSHA256";

    private final byte[] secretKey;

    public HmacSignatureVerifier(@Value("${enterprise-hub.security.hmac-secret}") String secret) {
        this.secretKey = secret.getBytes(StandardCharsets.UTF_8);
    }

    public boolean verify(String payload, String signatureHex) {
        if (payload == null || signatureHex == null) {
            return false;
        }
        try {
            Mac mac = Mac.getInstance(ALGORITHM);
            mac.init(new SecretKeySpec(secretKey, ALGORITHM));
            byte[] expected = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            byte[] actual = HexFormat.of().parseHex(signatureHex.trim().toLowerCase());
            return MessageDigest.isEqual(expected, actual);
        } catch (Exception e) {
            return false;
        }
    }
}
