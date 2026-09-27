package com.enterprisehub.security;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/** 每个 Controller 方法进来先调 {@link #require}——中央 Agent 不能靠"请求能连到这个接口"
 * 就默认有权限，必须显式检查 FastAPI 签的 scopes 里有没有这一条。 */
public final class ScopeGuard {
    private ScopeGuard() {
    }

    public static void require(String scope) {
        RequestContext ctx = RequestContextHolder.current();
        if (!ctx.hasScope(scope)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "缺少 scope: " + scope);
        }
    }
}
