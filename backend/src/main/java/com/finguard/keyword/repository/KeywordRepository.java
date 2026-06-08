package com.finguard.keyword.repository;

import com.finguard.keyword.domain.RiskKeyword;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface KeywordRepository extends JpaRepository<RiskKeyword,Long> {

    boolean existsByKeyword(String keyword); // 같은 키워드 이미 등록?
    List<RiskKeyword> findByActiveTrue(); // 문자 분석
}
