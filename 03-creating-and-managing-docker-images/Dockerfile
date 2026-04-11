# Stage 1: Build
FROM golang:1.24 AS build
# Set working directory
WORKDIR /src
# Copy go.mod and go.sum separately to leverage cache
COPY go.mod go.sum ./
# Download dependencies
RUN go mod download
# Copy the application source code
COPY . .
# Build the application
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /bin/hello ./main.go

# Stage 2: Run
FROM alpine:3.19
# Copy executable file
COPY --from=build /bin/hello /bin/hello
# Add a non-root user
RUN adduser -S rungo
# Change ownership of the executable file to the non-root user
RUN chown rungo /bin/hello
# Switch to the non-root use
USER rungo
# Run the application
CMD ["/bin/hello"]
