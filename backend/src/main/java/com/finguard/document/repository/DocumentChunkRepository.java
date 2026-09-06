package com.finguard.document.repository;

import com.finguard.document.domain.Document;
import com.finguard.document.domain.DocumentChunk;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface DocumentChunkRepository extends JpaRepository<DocumentChunk, Long> {
    List<DocumentChunk> findByDocumentOrderByChunkIndexAsc(Document document);

    void deleteByDocument(Document document);
    @Query("""
    select dc
    from DocumentChunk dc
    join fetch dc.document d
    where d.status = 'COMPLETED' and lower(dc.content) like lower(concat('%', :keyword, '%'))
    order by d.documentId asc, dc.chunkIndex asc
""")
    List<DocumentChunk> searchByKeyword(@Param("keyword") String keyword);
}
