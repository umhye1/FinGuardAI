package com.finguard.keyword.controller;

import com.finguard.global.response.CommonResponse;
import com.finguard.keyword.dto.request.KeywordCreateRequest;
import com.finguard.keyword.dto.request.KeywordScoreUpdateRequest;
import com.finguard.keyword.dto.request.KeywordUpdateRequest;
import com.finguard.keyword.dto.response.KeywordResponse;
import com.finguard.keyword.service.KeywordService;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/admin/keywords")
@RequiredArgsConstructor
public class KeywordController {

    private final KeywordService keywordService;

    @PostMapping
    public ResponseEntity<CommonResponse<KeywordResponse>> createKeyword(
            @RequestBody KeywordCreateRequest request
    ){
        KeywordResponse response = keywordService.createKeyword(request);

        return ResponseEntity.ok(
                CommonResponse.success(201,"위험 키워드 등록에 성공했습니다.",response)
        );
    }

    @GetMapping
    public ResponseEntity<CommonResponse<List<KeywordResponse>>> getAllKeywords(){
        List<KeywordResponse> response = keywordService.getAllKeywords();

        return ResponseEntity.ok(
                CommonResponse.success("위험 키워드 목록 조회에 성공했습니다.", response)
        );
    }

    @PutMapping("/{keywordId}")
    public ResponseEntity<CommonResponse<KeywordResponse>> updateKeyword(
            @PathVariable Long keywordId,
            @RequestBody KeywordUpdateRequest request
    ){
        KeywordResponse response = keywordService.updateKeyword(keywordId, request);

        return ResponseEntity.ok(
                CommonResponse.success("위험 키워드 수정에 성공했습니다.", response)
        );
    }

    @DeleteMapping("/{keywordId}")
    public ResponseEntity<CommonResponse<Void>> deleteKeyword(
            @PathVariable Long keywordId
    ){
        keywordService.deactivateKeyword(keywordId);

        return ResponseEntity.ok(
                CommonResponse.success("위험 키워드 비활성화에 성공했습니다")
        );
    }

    @PatchMapping("/{keywordId}/score")
    public ResponseEntity<CommonResponse<KeywordResponse>> updateRiskScore(
            @PathVariable Long keywordId,
            @RequestBody KeywordScoreUpdateRequest request
    ){
        KeywordResponse response = keywordService.updateRiskScore(keywordId, request);

        return ResponseEntity.ok(
                CommonResponse.success("위험 키워드 점수가 수정되었습니다.", response)
        );
    }



}
