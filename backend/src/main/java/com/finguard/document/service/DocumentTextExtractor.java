package com.finguard.document.service;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.stereotype.Component;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

@Component
public class DocumentTextExtractor {
    public String extract(String filePath) {
        try{
            String lowerFilePath = filePath.toLowerCase();

            if (lowerFilePath.endsWith(".txt")) {
                return extractTxt(filePath);
            }
            if (lowerFilePath.endsWith(".pdf")) {
                return extractPdf(filePath);
            }
            throw new IllegalArgumentException("지원하지 않는 파일 형식입니다.");

        }catch(Exception e){
            throw new IllegalArgumentException("문서 텍스트 추출 중 오류가 발생했습니다.");
        }
    }

    private String extractPdf(String filePath) throws Exception {
        File file = new File(filePath);

        try(PDDocument document = Loader.loadPDF(file)){
            PDFTextStripper stripper = new PDFTextStripper();
            return stripper.getText(document);
        }
    }

    private String extractTxt(String filePath) throws Exception{
        return Files.readString(
                Path.of(filePath),
                StandardCharsets.UTF_8
        );
    }
}
