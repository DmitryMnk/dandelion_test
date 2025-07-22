FROM postgres:alpine3.14

ARG USER_ID='1000'
ARG USER_ID=${USER_ID}
ENV USER_ID ${USER_ID}

ARG GROUP_ID='1000'
ARG GROUP_ID=${GROUP_ID}
ENV GROUP_ID ${GROUP_ID}
RUN apk --no-cache add shadow
RUN groupmod -g $USER_ID postgres
RUN usermod -u $USER_ID postgres
