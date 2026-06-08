package com.finguard.keyword.domain;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum KeywordCategory {
    INSTITUTION_IMPERSONATION("기관사칭"), // 기관 사칭
    PERSONAL_INFO_REQUEST("개인정보요구"),    // 개인정보 요구
    FINANCIAL_FRAUD("금융사기"),          // 금융 사기
    LINK_INDUCTION("링크유도"),           // 링크 유도
    THREAT("협박"),                   // 협박성 문구
    FAMILY_IMPERSONATION("가족사칭");     // 가족 사칭

    private final String label;

    @JsonValue
    public String getLabel(){
        return label;
    }

    @JsonCreator
    public static KeywordCategory from(String value){
        for(KeywordCategory category : KeywordCategory.values() ){
            if(category.label.equals(value) || category.name().equals(value)){
                return category;
            }
        }
        throw new IllegalArgumentException("존재하지 않는 키워드 카테고리입니다.");
    }

}
