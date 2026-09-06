package com.finguard.auth.controller;

import com.finguard.auth.dto.request.LoginRequest;
import com.finguard.auth.dto.request.LogoutRequest;
import com.finguard.auth.dto.request.SignupRequest;
import com.finguard.auth.dto.response.LoginResponse;
import com.finguard.auth.dto.response.MyInfoResponse;
import com.finguard.auth.dto.response.SignupResponse;
import com.finguard.auth.service.AuthService;
import com.finguard.global.response.CommonResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.RequestEntity;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {
    private final AuthService authService;

    @PostMapping("/signup")
    public ResponseEntity<CommonResponse<SignupResponse>> signup(@jakarta.validation.Valid @RequestBody SignupRequest request){
        SignupResponse response = authService.signup(request);
        return ResponseEntity.ok(
                CommonResponse.success("회원가입에 성공했습니다.", response));
    }


    @PostMapping("/login")
    public ResponseEntity<CommonResponse<LoginResponse>> login(@jakarta.validation.Valid @RequestBody LoginRequest request){
        LoginResponse response = authService.login(request);
        return ResponseEntity.ok(
                CommonResponse.success("로그인에 성공했습니다.", response)
        );
    }

    @PostMapping("/logout")
    public ResponseEntity<CommonResponse<Void>> logout(
            @RequestHeader("Authorization") String authorizationHeader,
            @jakarta.validation.Valid @RequestBody LogoutRequest request
    ){
        authService.logout(authorizationHeader,request);
        return ResponseEntity.ok(
                CommonResponse.success("로그아웃되었습니다.")
        );
    }

    @PostMapping("/refresh")
    public ResponseEntity<CommonResponse<LoginResponse>> refresh(
            @jakarta.validation.Valid @RequestBody com.finguard.auth.dto.request.RefreshRequest request) {
        return ResponseEntity.ok(CommonResponse.success("토큰을 재발급했습니다.", authService.refresh(request)));
    }

    @GetMapping("/me")
    public ResponseEntity<CommonResponse<MyInfoResponse>> getMyInfo(
            @RequestHeader("Authorization") String authorizationHeader
    ) {
      MyInfoResponse response = authService.getMyInfo(authorizationHeader);
      return ResponseEntity.ok(
              CommonResponse.success("내 정보 조회에 성공했습니다.", response)
      );
    }

}
