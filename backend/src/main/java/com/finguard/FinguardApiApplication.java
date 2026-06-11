package com.finguard;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication
public class FinguardApiApplication {

	@Value("${spring.servlet.multipart.max-file-size}")
	private String maxFileSize;

	@Value("${spring.servlet.multipart.max-request-size}")
	private String maxRequestSize;

	public static void main(String[] args) {
		SpringApplication.run(FinguardApiApplication.class, args);
	}

	@PostConstruct
	public void checkMultipartSetting() {
		System.out.println("max-file-size = " + maxFileSize);
		System.out.println("max-request-size = " + maxRequestSize);
	}
}