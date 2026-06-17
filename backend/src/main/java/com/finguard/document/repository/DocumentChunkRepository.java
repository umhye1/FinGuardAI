package com.finguard.document.repository;

import com.finguard.document.domain.Document;
import com.finguard.document.domain.DocumentChunk;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DocumentChunkRepository extends JpaRepository<DocumentChunk, Long> {
    List<DocumentChunk> findByDocumentOrderByChunkIndexAsc(Document document);

    void deleteByDocument(Document document);
}
