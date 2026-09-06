package com.finguard.auth;

import com.finguard.auth.controller.AuthController;
import com.finguard.auth.jwt.*;
import com.finguard.auth.service.*;
import com.finguard.global.config.SecurityConfig;
import com.finguard.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.security.test.context.support.WithMockUser;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(AuthController.class)
@Import({SecurityConfig.class, JwtAuthenticationFilter.class})
class AuthSecurityTest {
    @Autowired MockMvc mvc;
    @MockitoBean AuthService auth;
    @MockitoBean JwtTokenProvider tokens;
    @MockitoBean TokenSessionStore sessions;
    @MockitoBean UserRepository users;

    @Test void anonymousIsUnauthorized() throws Exception {
        mvc.perform(get("/api/auth/me")).andExpect(status().isUnauthorized());
    }
    @Test @WithMockUser(roles = "USER") void userCannotEnterAdmin() throws Exception {
        mvc.perform(get("/api/admin/documents")).andExpect(status().isForbidden());
    }
    @Test void refreshRejectsEmptyInputWithoutAuthentication() throws Exception {
        mvc.perform(post("/api/auth/refresh").contentType("application/json").content("{}"))
                .andExpect(status().isBadRequest());
    }
    @Test void signupValidatesInput() throws Exception {
        mvc.perform(post("/api/auth/signup").contentType("application/json")
                .content("{\"email\":\"invalid\",\"password\":\"short\",\"name\":\"\"}"))
                .andExpect(status().isBadRequest());
    }
}
