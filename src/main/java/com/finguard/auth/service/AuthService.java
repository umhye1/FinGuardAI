package com.finguard.auth.service;

import com.finguard.auth.dto.request.LoginRequest;
import com.finguard.auth.dto.request.LogoutRequest;
import com.finguard.auth.dto.response.LoginResponse;
import com.finguard.auth.dto.response.MyInfoResponse;
import com.finguard.auth.jwt.JwtTokenProvider;
import com.finguard.global.exception.DuplicateEmailException;
import com.finguard.global.exception.LoginFailedException;
import com.finguard.global.exception.UnauthorizedException;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.finguard.user.repository.UserRepository;
import com.finguard.user.domain.User;
import com.finguard.auth.dto.request.SignupRequest;
import com.finguard.auth.dto.response.SignupResponse;
import com.finguard.user.domain.UserRole;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true) // 조회 전용 트랜잭션(쓰기, 수정 등은 x). DB 작업을 하나의 안전한 작업 단위로 묶음
public class AuthService {

    private final UserRepository userRepository; // DB 접근 객체를 AuthService에서 사용하려고 주입받는 것
    private final PasswordEncoder passwordEncoder; // 비밀번호 암호화 위해 사용 - 나중에 로그인할 때는 입력한 비밀번호와 암호화된 비밀번호를 비교
    private final JwtTokenProvider jwtTokenProvider;

    @Transactional // 회원가입은 조회만 하면 안됨 - transactional 다시 붙임
    public SignupResponse signup(SignupRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {  // 이메일 정보 가져와서 존재하면
            throw new DuplicateEmailException("이미 가입된 이메일입니다.");
        }
        User user = User.builder()
                .email(request.getEmail())
                .password(passwordEncoder.encode(request.getPassword()))
                .name(request.getName())
                .role(UserRole.USER)
                .build();

        User savedUser = userRepository.save(user);

        return SignupResponse.from(savedUser);
    }

    @Transactional(readOnly = true)
    public LoginResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(()-> new LoginFailedException("이메일 또는 비밀번호가 올바르지 않습니다."));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new LoginFailedException("이메일 또는 비밀번호가 올바르지 않습니다.");
        }

        String accessToken = jwtTokenProvider.createAccessToken(
                user.getUserId(),
                user.getEmail(),
                user.getRole()
        );

        String refreshToken = jwtTokenProvider.createRefreshToken(
                user.getUserId(),
                user.getEmail()
        );

        return LoginResponse.of(user, accessToken, refreshToken);
    }

    @Transactional
    public void logout(String authorizationHeader, LogoutRequest request) {
        String accessToken = extractAccessToken(authorizationHeader);
        if (!jwtTokenProvider.validateToken(accessToken)) {
            throw new UnauthorizedException("로그아웃에 실패했습니다.");
        }

        if (request.getRefreshToken() == null || !jwtTokenProvider.validateToken(request.getRefreshToken())) {
            throw new UnauthorizedException("로그아웃에 실패했습니다.");
        }
    }

    private String extractAccessToken(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            throw new UnauthorizedException("인증 정보가 올바르지 않습니다.");
        }
        return authorizationHeader.substring(7);
    }

    @Transactional(readOnly = true)
    public MyInfoResponse getMyInfo(String authorizationHeader) {
        String accessToken = extractAccessToken(authorizationHeader);

        if(!jwtTokenProvider.validateToken(accessToken)) {
            throw new UnauthorizedException("내 정보 조회에 실패했습니다.");
        }

        String email = jwtTokenProvider.getEmail(accessToken);

        User user = userRepository.findByEmail(email)
                .orElseThrow(()-> new UnauthorizedException("내 정보 조회에 실패했습니다."));

        return MyInfoResponse.from(user);
    }
}
