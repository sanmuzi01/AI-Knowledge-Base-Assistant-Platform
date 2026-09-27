# 企业业务中心镜像。多阶段构建：先用带 Maven 的镜像编译出 jar，
# 运行阶段只留 JRE + jar，不带构建工具，镜像小很多。
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
# 先只拷 pom.xml 装依赖，源码没变时能复用这一层的 Docker 缓存。
COPY pom.xml .
RUN mvn -B dependency:go-offline
COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar
EXPOSE 8090
ENTRYPOINT ["java", "-jar", "app.jar"]
