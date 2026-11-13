# Çekirdek API imajı. Build context depo köküdür: sunucu arayüzleri packages/api-contract'tan üretilir.
#   docker build -f apps/api/Dockerfile -t meridian-api:local .
FROM eclipse-temurin:25-jdk AS build
WORKDIR /src
COPY packages/api-contract packages/api-contract
COPY apps/api/mvnw apps/api/pom.xml apps/api/
COPY apps/api/.mvn apps/api/.mvn
WORKDIR /src/apps/api
# Bağımlılıklar ayrı katmanda: kod değişince yeniden indirilmez.
RUN --mount=type=cache,target=/root/.m2 ./mvnw -B -q dependency:go-offline
COPY apps/api/src src
RUN --mount=type=cache,target=/root/.m2 ./mvnw -B -q -DskipTests package \
    && java -Djarmode=tools -jar target/api-0.0.1-SNAPSHOT.jar extract --layers --launcher --destination /layers

FROM eclipse-temurin:25-jre
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
# Seyrek değişen katmanlar önce: uygulama kodu en üstte.
COPY --from=build /layers/dependencies/ ./
COPY --from=build /layers/spring-boot-loader/ ./
COPY --from=build /layers/snapshot-dependencies/ ./
COPY --from=build /layers/application/ ./
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "org.springframework.boot.loader.launch.JarLauncher"]
