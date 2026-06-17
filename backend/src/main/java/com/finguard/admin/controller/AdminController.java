package com.finguard.admin.controller;

import com.finguard.admin.dto.response.AdminAnalysisLogResponse;
import com.finguard.admin.dto.response.AdminDashboardResponse;
import com.finguard.admin.dto.response.AuditLogResponse;
import com.finguard.admin.service.AdminService;
import com.finguard.global.response.CommonResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminController {
    private final AdminService adminService;

    @GetMapping("/audit-logs")
    public ResponseEntity<CommonResponse<List<AuditLogResponse>>> getAuditLogs() {
        List<AuditLogResponse> response = adminService.getAuditLogs();

        return ResponseEntity.ok(
                CommonResponse.success(200,"감사 로그 조회에 성공했습니다.", response)
        );
    }

    @GetMapping("/analysis-logs")
    public ResponseEntity<CommonResponse<List<AdminAnalysisLogResponse>>> getAnalysisLogs() {
       List<AdminAnalysisLogResponse> response = adminService.getAnalysisLogs();

       return ResponseEntity.ok(
               CommonResponse.success(200,"전체 분석 로그 조회에 성공했습니다.", response)
       );
    }

    @GetMapping("/dashboard")
    public ResponseEntity<CommonResponse<AdminDashboardResponse>> getDashboard() {
        AdminDashboardResponse response = adminService.getDashboard();

        return ResponseEntity.ok(
                CommonResponse.success(200, "관리자 대시보드 조회에 성공했습니다.", response)
        );
    }

}
