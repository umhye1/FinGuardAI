package com.finguard.document.controller;

import com.finguard.document.dto.request.DocumentCreateRequest;
import com.finguard.document.dto.response.DocumentCreateResponse;
import com.finguard.document.dto.response.DocumentDetailResponse;
import com.finguard.document.dto.response.DocumentListResponse;
import com.finguard.document.service.DocumentService;
import com.finguard.global.response.CommonResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/admin/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    // 1. 문서 업로드
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<CommonResponse<DocumentCreateResponse>> uploadDocument(
            @RequestParam("file") MultipartFile file,
            @RequestParam("title") String title,
            @RequestParam("source") String source,
            @RequestParam(value = "sourceUrl", required = false) String sourceUrl
    ){
        System.out.println("문서 업로드 컨트롤러 진입");
        System.out.println("file name = " + file.getOriginalFilename());
        System.out.println("file size = " + file.getSize());
        System.out.println("title = " + title);
        DocumentCreateRequest request = new DocumentCreateRequest(title, source, sourceUrl);

        DocumentCreateResponse response = documentService.createDocument(file, request);
        return ResponseEntity.status(201)
                .body(CommonResponse.success(201,"문서가 업로드되었습니다.", response));
    }

    // 2. 문서 목록 조회
    @GetMapping
    public ResponseEntity<CommonResponse<List<DocumentListResponse>>> getDocuments(){
        List<DocumentListResponse> response = documentService.getDocuments();

        return ResponseEntity.ok(
                CommonResponse.success(200,"문서 목록 조회에 성공했습니다,", response)
        );
    }

    // 3. 문서 상세 조회
    @GetMapping("/{documentId}")
    public ResponseEntity<CommonResponse<DocumentDetailResponse>> getDocument(@PathVariable Long documentId){
        DocumentDetailResponse response = documentService.getDocument(documentId);

        return ResponseEntity.ok(
                CommonResponse.success(200, "문서 상세 조회에 성공했습니다.",response)
        );
    }

    // 4. 문서 삭제
    @DeleteMapping("/{documentId}")
    public ResponseEntity<CommonResponse<Void>> deleteDocument(@PathVariable Long documentId){
        documentService.deleteDocument(documentId);
        return ResponseEntity.ok(
                CommonResponse.success("문서가 삭제되었습니다.")
        );
    }



}
