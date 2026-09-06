package com.finguard.document.service;

import com.finguard.audit.domain.AuditAction;
import com.finguard.audit.domain.AuditTargetType;
import com.finguard.audit.repository.AuditLogRepository;
import com.finguard.audit.service.AuditLogService;
import com.finguard.document.domain.Document;
import com.finguard.document.domain.DocumentStatus;
import com.finguard.document.dto.request.DocumentCreateRequest;
import com.finguard.document.dto.response.DocumentDetailResponse;
import com.finguard.document.dto.response.DocumentListResponse;
import com.finguard.document.dto.response.DocumentCreateResponse;
import com.finguard.document.repository.DocumentChunkRepository;
import com.finguard.document.repository.DocumentRepository;
import com.finguard.global.exception.BadRequestException;
import com.finguard.global.exception.NotFoundException;
import com.finguard.user.domain.User;
import com.finguard.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DocumentService {

    private final DocumentRepository documentRepository;
    private final UserRepository userRepository;
    private final com.finguard.job.service.DocumentJobService jobs;
    private final com.finguard.job.repository.ProcessingJobRepository jobRepository;
    private final com.fasterxml.jackson.databind.ObjectMapper objectMapper;
    private final AuditLogService auditLogService;
    private final DocumentChunkRepository documentChunkRepository;


    @Value("${file.upload-dir:./uploads}")
    private String uploadDir;

    @Transactional
    public DocumentCreateResponse createDocument(
            MultipartFile file,
            DocumentCreateRequest request,
            String ipAddress
    ) {
        validateFile(file);
        if (request.getTitle() == null || request.getTitle().isBlank() || request.getTitle().length() > 255
                || request.getSource() == null || request.getSource().isBlank() || request.getSource().length() > 100) {
            throw new BadRequestException("문서 제목과 출처를 올바르게 입력해주세요.");
        }

        User user = getCurrentUser();

        String originalFileName = file.getOriginalFilename();
        String storedFileName = createdStoredFileName(originalFileName);
        String filePath = saveFile(file,storedFileName);
        org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                new org.springframework.transaction.support.TransactionSynchronization() {
                    @Override public void afterCompletion(int status) {
                        if (status != STATUS_COMMITTED) {
                            try { deleteFile(filePath); }
                            catch (Exception e) { org.slf4j.LoggerFactory.getLogger(DocumentService.class)
                                    .warn("Rolled-back upload requires file cleanup"); }
                        }
                    }
                });

        Document document = Document.builder()
                .title(request.getTitle())
                .source(request.getSource())
                .sourceUrl(request.getSourceUrl())
                .originalFileName(originalFileName)
                .storedFileName(storedFileName)
                .filePath(filePath)
                .status(DocumentStatus.UPLOADED)
                .chunkCount(0)
                .uploadedBy(user)
                .build();

        Document savedDocument = documentRepository.saveAndFlush(document);

        UUID jobId = jobs.enqueue(savedDocument.getDocumentId(), user.getUserId());

        // 감사 로그 저장
        auditLogService.saveLog(
                user,
                AuditAction.UPLOAD_DOCUMENT,
                AuditTargetType.DOCUMENT,
                savedDocument.getDocumentId(),
                ipAddress,
            auditDetail(savedDocument.getTitle())
        );

        return DocumentCreateResponse.from(savedDocument, jobId);
    }


    public List<DocumentListResponse> getDocuments(){
        return documentRepository.findAllByOrderByCreatedAtDesc()
                .stream()
                .map(DocumentListResponse::from)
                .toList();
    }

    public DocumentDetailResponse getDocument(Long documentId){
        Document document = getDocumentById(documentId);

        return DocumentDetailResponse.from(document);
    }

    @Transactional
    public void deleteDocument(Long documentId, String ipAddress){
        Document document = documentRepository.findLocked(documentId)
                .orElseThrow(() -> new NotFoundException("문서를 찾을 수 없습니다."));
        if (jobRepository.existsByDocumentIdAndStatusIn(documentId, List.of(
                com.finguard.job.domain.ProcessingJob.Status.PENDING, com.finguard.job.domain.ProcessingJob.Status.RUNNING))) {
            throw new com.finguard.global.exception.ConflictException("처리 중인 문서는 삭제할 수 없습니다.");
        }
        User user = getCurrentUser();

        String title  = document.getTitle();

        documentChunkRepository.deleteByDocument(document);

        String pathToDelete = document.getFilePath();
        org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                new org.springframework.transaction.support.TransactionSynchronization() {
                    @Override public void afterCommit() {
                        try { deleteFile(pathToDelete); }
                        catch (Exception e) { org.slf4j.LoggerFactory.getLogger(DocumentService.class)
                                .warn("Orphan document file requires cleanup: documentId={}", documentId); }
                    }
                });
        jobRepository.deleteByDocumentId(documentId);

        documentRepository.delete(document);

        auditLogService.saveLog(
                user,
                AuditAction.DELETE_DOCUMENT,
                AuditTargetType.DOCUMENT,
                documentId,
                ipAddress,
                auditDetail(title)
        );

    }

    private void validateFile(MultipartFile file) {
        if(file == null || file.isEmpty()) {
            throw new BadRequestException("업로드할 문서를 선택해주세요.");
        }

        String originalFileName = file.getOriginalFilename();

        if (originalFileName==null || originalFileName.isBlank()) {
            throw new BadRequestException("파일명이 올바르지 않습니다.");
        }


        String lower = originalFileName.toLowerCase(java.util.Locale.ROOT);
        if ((!lower.endsWith(".pdf") && !lower.endsWith(".txt")) || originalFileName.length() > 255) {
            throw new BadRequestException("PDF 또는 TXT 파일만 업로드할 수 있습니다.");
        }
        if (file.getSize() > 10 * 1024 * 1024) throw new BadRequestException("파일은 10MB 이하여야 합니다.");
    }

    @Transactional
    public UUID retry(Long documentId) {
        return jobs.enqueue(documentId, getCurrentUser().getUserId());
    }

    private String auditDetail(String title) {
        try { return objectMapper.writeValueAsString(java.util.Map.of("title", title)); }
        catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw new IllegalStateException(e); }
    }

    private String createdStoredFileName(String originalFileName) {
        String extension = originalFileName.substring(originalFileName.lastIndexOf("."));
        return UUID.randomUUID() + extension;
    }

    private String saveFile(MultipartFile file, String storedFileName) {
        try {
            Path uploadPath = Paths.get(uploadDir)
                    .toAbsolutePath()
                    .normalize();

            Files.createDirectories(uploadPath);

            Path filePath = uploadPath
                    .resolve(storedFileName)
                    .normalize();

            file.transferTo(filePath);

            return filePath.toString();
        } catch (Exception e) {
            throw new IllegalStateException("문서 파일 저장 중 오류가 발생했습니다.", e);
        }
    }

    private void deleteFile(String filePath) {
        try{
            Files.deleteIfExists(Paths.get(filePath));
        }catch (Exception e) {
            throw new IllegalStateException("문서 파일 삭제 중 오류가 발생했습니다.", e);
        }
    }

    private Document getDocumentById(Long documentId) {
        return documentRepository.findById(documentId)
                .orElseThrow(()-> new NotFoundException("문서를 찾을 수 없습니다."));
    }

    private User getCurrentUser(){
        String email = SecurityContextHolder.getContext()
                .getAuthentication()
                .getName();

        return userRepository.findByEmail(email)
                .orElseThrow(()->new NotFoundException("사용자를 찾을 수 없습니다."));
    }
}
