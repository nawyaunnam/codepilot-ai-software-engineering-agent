FROM golang:1.23-alpine AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /sandbox .
FROM alpine:3.21
RUN apk add --no-cache python3 py3-pytest nodejs npm && adduser -D runner
COPY --from=build /sandbox /sandbox
USER runner
ENTRYPOINT ["/sandbox"]

