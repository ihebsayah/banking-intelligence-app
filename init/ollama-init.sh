#!/bin/bash
# Wait for Ollama to be ready
sleep 5
# Pull mistral model
docker exec banking_ollama ollama pull mistral
echo "✅ Mistral model ready"
