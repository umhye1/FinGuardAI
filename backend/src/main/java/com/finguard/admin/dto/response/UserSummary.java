package com.finguard.admin.dto.response;

import com.finguard.user.domain.User;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class UserSummary {
    private Long userId;
    private String email;
    private String name;

    public static UserSummary from(User user){
        return UserSummary.builder()
                .userId(user.getUserId())
                .email(user.getEmail())
                .name(user.getName())
                .build();
    }
}
