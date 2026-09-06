package com.finguard;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
public class FinguardApiApplication {
    public static void main(String[] args) {
        SpringApplication.run(FinguardApiApplication.class, args);
    }
}
