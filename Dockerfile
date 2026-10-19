ARG BUILD_TOOLS_VERSION="36.0.0"
ARG APKTOOL_VERSION="2.11.1"

FROM python:3.13-slim

ARG BUILD_TOOLS_VERSION
ARG APKTOOL_VERSION

WORKDIR /xapktoapk
COPY xapktoapk.py docker/entrypoint.sh ./

# Dependencies: wget, java, keytool, zipalign, apksigner, apktool
RUN apt update && apt -y install wget sdkmanager default-jdk-headless
RUN sdkmanager --install "build-tools;${BUILD_TOOLS_VERSION}"
ENV PATH="$PATH:/opt/android-sdk/build-tools/${BUILD_TOOLS_VERSION}"
RUN \
	wget -q https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool -O /usr/local/bin/apktool && \
	wget -q https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_${APKTOOL_VERSION}.jar -O /usr/local/bin/apktool.jar && \
	chmod +x /usr/local/bin/apktool /usr/local/bin/apktool.jar

ENTRYPOINT [ "./entrypoint.sh" ]