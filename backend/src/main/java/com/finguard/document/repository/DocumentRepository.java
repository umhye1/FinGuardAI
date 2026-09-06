package com.finguard.document.repository;

import com.finguard.document.domain.Document;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface DocumentRepository extends JpaRepository<Document, Long> {

    @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
    @org.springframework.data.jpa.repository.Query("select d from Document d where d.documentId = :id")
    java.util.Optional<Document> findLocked(@org.springframework.data.repository.query.Param("id") Long id);

    List<Document> findAllByOrderByCreatedAtDesc();
}
