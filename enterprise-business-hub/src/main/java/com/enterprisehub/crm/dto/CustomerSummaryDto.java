package com.enterprisehub.crm.dto;

import java.util.List;

/** 销售 Agent 生成客户摘要用的原始数据（设计稿："获取联系人和历史跟进 → 销售Agent
 * 生成客户摘要"——摘要本身是 Agent 拿这份数据自己生成，这里只负责把数据给全）。 */
public record CustomerSummaryDto(
        long id,
        String name,
        String industry,
        long ownerUserId,
        long teamId,
        List<ContactDto> contacts,
        List<FollowUpDto> recentFollowUps,
        List<OpportunityDto> opportunities
) {
    public record ContactDto(String name, String title, String phone, String email) {
    }
}
