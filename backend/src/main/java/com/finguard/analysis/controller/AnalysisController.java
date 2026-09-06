package com.finguard.analysis.controller;

import com.finguard.analysis.dto.request.AnalysisRequest;
import com.finguard.analysis.dto.response.AnalysisDetailResponse;
import com.finguard.analysis.dto.response.AnalysisHistoryResponse;
import com.finguard.analysis.dto.response.AnalysisResponse;
import com.finguard.analysis.service.AnalysisService;
import com.finguard.global.response.CommonResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/analysis")
@RequiredArgsConstructor
public class AnalysisController {

    private final AnalysisService analysisService;

    @PostMapping
    public ResponseEntity<CommonResponse<AnalysisResponse>> analyze(
            @jakarta.validation.Valid @RequestBody AnalysisRequest request
    ){
        AnalysisResponse response = analysisService.analyze(request);

        return ResponseEntity.ok(
                CommonResponse.success(200,"의심 문자 분석이 완료되었습니다.", response)
        );
    }

    @GetMapping
    public ResponseEntity<CommonResponse<List<AnalysisHistoryResponse>>> getHistories(){
        List<AnalysisHistoryResponse> response = analysisService.getHistories();

        return ResponseEntity.ok(
                CommonResponse.success(200,"분석 이력 조회에 성공했습니다.",response)
        );
    }

    @GetMapping("/{analysisId}")
    public ResponseEntity<CommonResponse<AnalysisDetailResponse>> getDetail(
            @PathVariable Long analysisId
    ){
        AnalysisDetailResponse response = analysisService.getDetail(analysisId);

        return ResponseEntity.ok(
                CommonResponse.success(200,"분석 상세 조회에 성공했습니다.", response)
        );
    }

    @DeleteMapping("/{analysisId}")
    public ResponseEntity<CommonResponse<Void>> deleteAnalysis(
            @PathVariable Long analysisId
    ){
        analysisService.deleteAnalysis(analysisId);
        return ResponseEntity.ok(
                CommonResponse.success(200,"분석 이력이 삭제되었습니다.",null)
        );
    }

}

