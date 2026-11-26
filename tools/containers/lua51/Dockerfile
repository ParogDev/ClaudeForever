# Lua 5.1 toolbox for addon checks: luacheck, busted, stylua. One image for tools\lua.ps1 on the
# dev PC and for the CI runner (tools/ci/runner/Dockerfile copies the same tool list), so a green
# local run means a green CI run. WoW's Lua is 5.1 (with bit, without goto/io/os), so 5.1, not 5.4.
#
# tools\lua.ps1 builds this with --label wowf.dockerfile.sha256=<hash of this file> and rebuilds when the hash
# differs, so editing a pin here is enough: the next tools\lua.ps1 run picks it up, locally and with -Remote.
FROM ubuntu:24.04

ARG STYLUA_VERSION=2.1.0
ARG LUACHECK_VERSION=1.2.0-1
ARG BUSTED_VERSION=2.3.0-1
LABEL wowf.pins="stylua=${STYLUA_VERSION} luacheck=${LUACHECK_VERSION} busted=${BUSTED_VERSION}"
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      lua5.1 liblua5.1-0-dev luarocks ca-certificates curl unzip build-essential git \
 && rm -rf /var/lib/apt/lists/*

RUN luarocks --lua-version 5.1 install luacheck "${LUACHECK_VERSION}" \
 && luarocks --lua-version 5.1 install busted "${BUSTED_VERSION}" \
 && luarocks --lua-version 5.1 install luafilesystem

RUN curl -fsSL -o /tmp/stylua.zip \
      "https://github.com/JohnnyMorganz/StyLua/releases/download/v${STYLUA_VERSION}/stylua-linux-x86_64.zip" \
 && unzip -q /tmp/stylua.zip -d /usr/local/bin && rm /tmp/stylua.zip && chmod +x /usr/local/bin/stylua

# The repo is mounted at /work; commands run from there (tools\lua.ps1 sets the subfolder).
WORKDIR /work
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["luacheck --version && busted --version && stylua --version"]
