package com.finguard.document.service;


import com.finguard.document.domain.Document;
import com.finguard.document.domain.DocumentChunk;
import com.finguard.document.dto.response.DocumentChunkSearchResponse;
import com.finguard.document.repository.DocumentChunkRepository;
import com.finguard.global.exception.BadRequestException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DocumentChunkService {

    private final int CHUNK_SIZE = 800;
    private final DocumentChunkRepository documentChunkRepository;

    @Transactional
    public int createChunks(Document document, String text) {
        if(text == null || text.isBlank()){
            return 0;
        }
        List<DocumentChunk> chunks = splitText(document, text);
        documentChunkRepository.saveAll(chunks);
        return chunks.size();
    }

    private List<DocumentChunk> splitText(Document document, String text) {
        List<DocumentChunk> chunks = new ArrayList<>();

        String nomalizedText = nomalizeText(text);

        int chunkIndex = 0;

        for (int start = 0; start < nomalizedText.length(); start += CHUNK_SIZE ) {
            int end = Math.min(start + CHUNK_SIZE, nomalizedText.length());

            String content = nomalizedText.substring(start, end);

            DocumentChunk chunk = DocumentChunk.builder()
                    .document(document)
                    .chunkIndex(chunkIndex)
                    .content(content)
                    .build();

            chunks.add(chunk);
            chunkIndex++;
        }
        return chunks;
    }

    private String nomalizeText(String text) {
        return text
                .replaceAll("\\s+"," ")
                .trim();
    }

    public List<DocumentChunkSearchResponse> searchChunks(String keyword) {
        if(keyword == null || keyword.isBlank()){
            throw new BadRequestException("검색 키워드를 입력해주세요.");
        }

        return documentChunkRepository.searchByKeyword(keyword.trim())
                .stream()
                .map(DocumentChunkSearchResponse::from)
                .toList();
    }


}
