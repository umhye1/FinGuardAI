package com.finguard.document.domain;

import com.finguard.user.domain.User;
import jakarta.persistence.*;
import lombok.*;
import lombok.extern.apachecommons.CommonsLog;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "documents")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class Document {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE,generator = "documents_seq_generator")
    @SequenceGenerator(
            name = "documents_seq_generator",
            sequenceName ="document_seq",
            allocationSize = 1
    )
    @Column(name = "document_id")
    private Long documentId;

    @Column(name = "title", nullable = false,length = 255)
    private String title;

    @Column(name = "source", length = 100)
    private String source;

    @Column(name = "source_url",  columnDefinition = "TEXT")
    private String sourceUrl;

    @Column(name = "file_path", nullable = false, columnDefinition = "TEXT")
    private String filePath;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 30)
    private DocumentStatus status;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "uploaded_by")
    private User uploadedBy;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;


    @Column(name = "original_file_name", nullable = false, length = 255)
    private String originalFileName;

    @Column(name = "stored_file_name", nullable = false, length = 255)
    private String storedFileName;

    @Column(name = "chunk_count", nullable = false)
    private int chunkCount;


    public void updateStatus(DocumentStatus status) {
        this.status = status;
    }

    public void updateChunkCount(int chunkCount) {
        this.chunkCount = chunkCount;
    }

    public void completeProcessing(int chunkCount) {
        this.status = DocumentStatus.COMPLETED;
        this.chunkCount = chunkCount;
    }

    public void failProcessing() {
        this.status = DocumentStatus.FAILED;
    }




}
