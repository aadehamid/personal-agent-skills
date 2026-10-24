# Apache Jena Fuseki 6.2.0 for add-on J (references/add-ons.md). Jena publishes a Dockerfile in
# its jena-fuseki-docker package, not an image. This file fetches that package, checks it against
# the pinned SHA-256, and builds from it as Jena's Dockerfile does: Jena's download.sh fetches the
# server jar and checks it against Maven Central's SHA-1.
#   docker compose --profile fuseki build      (from the docker/ folder)

ARG JENA_VERSION=6.2.0
ARG JAVA_VERSION=21
ARG ALPINE_IMAGE=alpine:3.21.2@sha256:56fa17d2a7e7f168a043a2712e63aed1f8543aeafdcee47c58dcffe38ed51099

## ---- Stage 1: the jena-fuseki-docker package, checked.
FROM ${ALPINE_IMAGE} AS package
ARG JENA_VERSION
ARG PACKAGE_SHA256=7a2dbc918a02adaba2a398c7cebf64c85a42d9a6717ade814acc14ca27d71c66
WORKDIR /pkg
RUN wget -q -O package.zip \
      "https://repo1.maven.org/maven2/org/apache/jena/jena-fuseki-docker/${JENA_VERSION}/jena-fuseki-docker-${JENA_VERSION}.zip" \
 && echo "${PACKAGE_SHA256}  package.zip" | sha256sum -c - \
 && unzip -q package.zip && mv "jena-fuseki-docker-${JENA_VERSION}" src

## ---- Stage 2: the server jar and a reduced Java runtime (Jena's Dockerfile, stage "base").
FROM eclipse-temurin:${JAVA_VERSION}-alpine AS base
ARG JENA_VERSION
ARG FUSEKI_JAR=jena-fuseki-server-${JENA_VERSION}.jar
RUN apk add --no-cache curl binutils
WORKDIR /fuseki
COPY --from=package /pkg/src/download.sh /pkg/src/entrypoint.sh /pkg/src/log4j2.properties ./
RUN chmod a+x download.sh entrypoint.sh \
 && ./download.sh --chksum sha1 \
      "https://repo1.maven.org/maven2/org/apache/jena/jena-fuseki-server/${JENA_VERSION}/${FUSEKI_JAR}" \
 && rm download.sh
RUN JDEPS="$(jdeps --multi-release base --print-module-deps --ignore-missing-deps ${FUSEKI_JAR})" \
 && jlink --compress 2 --strip-debug --no-header-files --no-man-pages --output /opt/java-minimal \
      --add-modules "${JDEPS},jdk.crypto.cryptoki,jdk.crypto.ec,jdk.localedata"

## ---- Stage 3: the runtime (Jena's Dockerfile, last stage).
FROM ${ALPINE_IMAGE}
ARG JENA_VERSION
COPY --from=base /opt/java-minimal /opt/java-minimal
COPY --from=base /fuseki /fuseki
WORKDIR /fuseki
RUN addgroup -g 1000 fuseki && adduser fuseki -G fuseki -s /bin/ash -u 1000 -H -D \
 && mkdir -p /fuseki/logs /fuseki/databases && chown -R fuseki /fuseki
USER fuseki
ENV JAVA_HOME=/opt/java-minimal JAVA_OPTIONS="-Xmx1g -Xms1g" JENA_VERSION=${JENA_VERSION} \
    FUSEKI_JAR=jena-fuseki-server-${JENA_VERSION}.jar FUSEKI_DIR=/fuseki
EXPOSE 3030
ENTRYPOINT ["./entrypoint.sh"]
CMD []
