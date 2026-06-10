package com.finguard.keyword.service;

import com.finguard.keyword.domain.RiskKeyword;
import com.finguard.keyword.dto.request.KeywordCreateRequest;
import com.finguard.keyword.dto.request.KeywordScoreUpdateRequest;
import com.finguard.keyword.dto.request.KeywordUpdateRequest;
import com.finguard.keyword.dto.response.KeywordResponse;
import com.finguard.keyword.repository.KeywordRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class KeywordService {
    private final KeywordRepository keywordRepository;

    // keyword 등록하기
    @Transactional
    public KeywordResponse createKeyword(KeywordCreateRequest request) {
        if(keywordRepository.existsByKeyword(request.getKeyword())){
            throw new IllegalArgumentException("이미 등록된 키워드 입니다.");
        }

        RiskKeyword riskKeyword = RiskKeyword.builder()
                .keyword(request.getKeyword())
                .riskScore(request.getRiskScore())
                .category(request.getCategory())
                .description(request.getDescription())
                .active(true)
                .build();

        RiskKeyword savedKeyword = keywordRepository.save(riskKeyword);

        return KeywordResponse.from(savedKeyword);
    }


    // 키워드 목록 조회
    public List<KeywordResponse> getAllKeywords() {
        return keywordRepository.findAll()
                .stream()
                .map(KeywordResponse::from)
                .toList();
    }


    @Transactional
    public KeywordResponse updateKeyword(Long keywordId, KeywordUpdateRequest request) {
        RiskKeyword riskKeyword =  keywordRepository.findById(keywordId)
                .orElseThrow(()-> new IllegalArgumentException("키워드를 찾을 수 없습니다."));

        riskKeyword.update(
                request.getKeyword(),
                request.getRiskScore(),
                request.getCategory(),
                request.getDescription(),
                request.isActive()
        );

        return KeywordResponse.from(riskKeyword);
    }

    @Transactional
    public void deactivateKeyword(Long keywordId) {
        RiskKeyword riskKeyword = keywordRepository.findById(keywordId)
                .orElseThrow(()-> new IllegalArgumentException("키워드를 찾을 수 없습니다."));

        riskKeyword.deactivate();

    }

    @Transactional
    public KeywordResponse updateRiskscore(Long keywordId, KeywordScoreUpdateRequest request) {
        RiskKeyword riskKeyword = keywordRepository.findById(keywordId)
                .orElseThrow(()-> new IllegalArgumentException("키워드를 찾을 수 없습니다."));

        riskKeyword.updateRiskScore(request.getRiskScore());

        return KeywordResponse.from(riskKeyword);
    }

}
