package com.finguard.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.finguard.auth.dto.request.*;
import com.finguard.auth.jwt.JwtTokenProvider;
import com.finguard.auth.service.*;
import com.finguard.global.exception.UnauthorizedException;
import com.finguard.user.domain.*;
import com.finguard.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;
import java.util.Optional;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class TokenLifecycleTest {
    JwtTokenProvider tokens = new JwtTokenProvider();
    TokenSessionStore sessions = mock(TokenSessionStore.class);
    UserRepository users = mock(UserRepository.class);
    AuthService auth;
    @BeforeEach void setup() {
        ReflectionTestUtils.setField(tokens, "secret", "test-key-0123456789012345678901234567890123456789");
        ReflectionTestUtils.setField(tokens, "accessTokenExpiration", 60000L);
        ReflectionTestUtils.setField(tokens, "refreshTokenExpiration", 120000L);
        tokens.init();
        auth = new AuthService(users, mock(PasswordEncoder.class), tokens, sessions);
    }
    @Test void tokensHaveDistinctTypesAndUniqueIds() {
        String access = tokens.createAccessToken(1L, "user@test.dev", UserRole.USER, "s1");
        String refresh = tokens.createRefreshToken(1L, "user@test.dev", "s1");
        assertThat(tokens.validateAccessToken(access)).isTrue();
        assertThat(tokens.validateAccessToken(refresh)).isFalse();
        assertThat(tokens.validateRefreshToken(access)).isFalse();
        assertThat(tokens.validateAccessToken("invalid")).isFalse();
        assertThat(refresh).isNotEqualTo(tokens.createRefreshToken(1L, "user@test.dev", "s1"));
    }
    @Test void reusedRefreshIsRejected() {
        String old = tokens.createRefreshToken(1L, "user@test.dev", "s1");
        when(users.findById(1L)).thenReturn(Optional.of(User.builder().userId(1L)
                .email("user@test.dev").role(UserRole.USER).build()));
        when(sessions.rotate(eq("s1"), eq(old), anyString(), anyLong())).thenReturn(true, false);
        assertThat(auth.refresh(new RefreshRequest(old)).getAccessToken()).isNotBlank();
        assertThatThrownBy(() -> auth.refresh(new RefreshRequest(old))).isInstanceOf(UnauthorizedException.class);
    }
    @Test void logoutRejectsAnotherSessionThenRevokesMatchingSession() throws Exception {
        String access = tokens.createAccessToken(1L, "user@test.dev", UserRole.USER, "s1");
        String other = tokens.createRefreshToken(1L, "user@test.dev", "s2");
        ObjectMapper mapper = new ObjectMapper();
        LogoutRequest mismatch = mapper.readValue("{\"refreshToken\":\"" + other + "\"}", LogoutRequest.class);
        assertThatThrownBy(() -> auth.logout("Bearer " + access, mismatch)).isInstanceOf(UnauthorizedException.class);
        verifyNoInteractions(sessions);
        String refresh = tokens.createRefreshToken(1L, "user@test.dev", "s1");
        auth.logout("Bearer " + access, mapper.readValue("{\"refreshToken\":\"" + refresh + "\"}", LogoutRequest.class));
        verify(sessions).revoke("s1");
    }
}
