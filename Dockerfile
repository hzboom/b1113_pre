# Use Eclipse Temurin JDK for Java development
FROM eclipse-temurin:17-jdk

# Set working directory
WORKDIR /app

# Copy source files
COPY . /app/

# Install any additional development tools
RUN apt-get update && apt-get install -y \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Default to bash shell for development
CMD ["/bin/bash"]