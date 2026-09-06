FROM gradle:8.14.4-jdk21 AS build
WORKDIR /workspace
COPY build.gradle settings.gradle ./
COPY src ./src
RUN gradle bootJar --no-daemon

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --uid 10001 --create-home app && mkdir /app/uploads && chown app /app/uploads
COPY --from=build /workspace/build/libs/finguard-api-0.0.1-SNAPSHOT.jar /app/app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
