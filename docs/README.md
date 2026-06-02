# docs

Architecture and design notes.

- **Overview:** an AWS-native, multimodal video RAG platform — async ingestion,
  separate visual/transcript Pinecone indexes, a LangGraph query pipeline,
  Bedrock generation with timestamped citations and no-answer behavior, and a
  RAGAS + custom-metric evaluation suite.
- **Data flow, retrieval design, and the evaluation plan** are documented here
  as the corresponding parts of the system land.
