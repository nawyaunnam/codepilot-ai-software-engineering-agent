FROM golang:1.23-alpine AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /sandbox .
FROM docker:27-cli
COPY --from=build /sandbox /sandbox
ENTRYPOINT ["/sandbox"]
