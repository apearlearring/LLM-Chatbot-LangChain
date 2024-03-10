import base64
import random
from io import BytesIO
from typing import List, Tuple, Union

import streamlit as st
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_community.chat_models import BedrockChat
from langchain_core.messages import AIMessage, HumanMessage
from langchain.callbacks.base import BaseCallbackHandler
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts.chat import ChatPromptTemplate, MessagesPlaceholder
from PIL import Image

MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

CLAUDE_PROMPT = ChatPromptTemplate.from_messages(
    [
        MessagesPlaceholder(variable_name="history"),
        MessagesPlaceholder(variable_name="input"),
    ]
)

INIT_MESSAGE = {
    "role": "assistant",
    "content": "Hi! I'm Claude on Bedrock. How may I help you?",
}

SYSTEM_PROMPT = "You're a cool assistant, love to response with emoji."


class StreamHandler(BaseCallbackHandler):
    """
    Callback handler to stream the generated text to Streamlit.
    """

    def __init__(self, container: st.container) -> None:
        self.container = container
        self.text = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        Append the new token to the text and update the Streamlit container.
        """
        self.text += token
        self.container.markdown(self.text)


def set_page_config() -> None:
    """
    Set the Streamlit page configuration.
    """
    st.set_page_config(page_title="🤖 Chat with Bedrock", layout="wide")
    st.title("🤖 Chat with Bedrock")


def get_sidebar_params() -> Tuple[float, float, int, int, int]:
    """
    Get inference parameters from the sidebar.
    """
    with st.sidebar:
        st.markdown("## Inference Parameters")
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=1.0,
            step=0.1,
            key=f"{st.session_state['widget_key']}_Temperature",
        )
        top_p = st.slider(
            "Top-P",
            min_value=0.0,
            max_value=1.0,
            value=1.00,
            step=0.01,
            key=f"{st.session_state['widget_key']}_Top-P",
        )
        top_k = st.slider(
            "Top-K",
            min_value=1,
            max_value=500,
            value=500,
            step=5,
            key=f"{st.session_state['widget_key']}_Top-K",
        )
        max_tokens = st.slider(
            "Max Token",
            min_value=0,
            max_value=4096,
            value=4096,
            step=8,
            key=f"{st.session_state['widget_key']}_Max Token",
        )
        memory_window = st.slider(
            "Memory Window",
            min_value=0,
            max_value=10,
            value=10,
            step=1,
            key=f"{st.session_state['widget_key']}_Memory Window",
        )

    return temperature, top_p, top_k, max_tokens, memory_window


def init_conversationchain(
    temperature: float,
    top_p: float,
    top_k: int,
    max_tokens: int,
    memory_window: int,
) -> ConversationChain:
    """
    Initialize the ConversationChain with the given parameters.
    """
    model_kwargs = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
    }

    llm = BedrockChat(model_id=MODEL_ID, model_kwargs=model_kwargs, streaming=True)

    conversation = ConversationChain(
        llm=llm,
        verbose=True,
        memory=ConversationBufferWindowMemory(
            k=memory_window,
            ai_prefix="Assistant",
            chat_memory=StreamlitChatMessageHistory(),
            return_messages=True,
        ),
        prompt=CLAUDE_PROMPT,
    )

    # Store LLM generated responses
    if "messages" not in st.session_state:
        st.session_state.messages = [INIT_MESSAGE]

    return conversation


def generate_response(
    conversation: ConversationChain, input: Union[str, List[dict]]
) -> str:
    """
    Generate a response from the conversation chain with the given input.
    """
    return conversation.invoke(
        {"input": input}, {"callbacks": [StreamHandler(st.empty())]}
    )


def new_chat() -> None:
    """
    Reset the chat session and initialize a new conversation chain.
    """
    st.session_state["messages"] = [INIT_MESSAGE]
    st.session_state["langchain_messages"] = []
    st.session_state["file_uploader_key"] = random.randint(1, 100)


def display_chat_messages(uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile]) -> None:
    """
    Display chat messages and uploaded images in the Streamlit app.
    """
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if uploaded_files:
                if "images" in message and message["images"]:
                    num_cols = 10
                    cols = st.columns(num_cols)
                    i = 0

                    for image_id in message["images"]:
                        for uploaded_file in uploaded_files:
                            if image_id == uploaded_file.file_id:
                                img = Image.open(uploaded_file)

                                with cols[i]:
                                    st.image(img, caption="", width=75)
                                    i += 1

                                if i >= num_cols:
                                    i = 0

            if message["role"] == "user":
                if isinstance(message["content"], str):
                    st.markdown(message["content"])
                elif isinstance(message["content"], dict):
                    st.markdown(message["content"]["input"][0]["content"][0]["text"])
                else:
                    st.markdown(message["content"][0]["text"])

            if message["role"] == "assistant":
                if isinstance(message["content"], str):
                    st.markdown(message["content"])
                elif "response" in message["content"]:
                    st.markdown(message["content"]["response"])


def langchain_messages_format(messages: List[Union[AIMessage, HumanMessage]]) -> List[Union[AIMessage, HumanMessage]]:
    """
    Format the messages for the LangChain conversation chain.
    """
    for i, message in enumerate(messages):
        if isinstance(message.content, list):
            if "role" in message.content[0]:
                if message.type == "ai":
                    message = AIMessage(message.content[0]["content"])
                if message.type == "human":
                    message = HumanMessage(message.content[0]["content"])
                messages[i] = message
    return messages


def main() -> None:
    """
    Main function to run the Streamlit app.
    """
    set_page_config()

    # Generate a unique widget key only once
    if "widget_key" not in st.session_state:
        st.session_state["widget_key"] = str(random.randint(1, 1000000))

    temperature, top_p, top_k, max_tokens, memory_window = get_sidebar_params()
    conv_chain = init_conversationchain(temperature, top_p, top_k, max_tokens, memory_window)

    # Add a button to start a new chat
    st.sidebar.button("New Chat", on_click=new_chat, type="primary")

    # Image uploader
    if "file_uploader_key" not in st.session_state:
        st.session_state["file_uploader_key"] = 0

    uploaded_files = st.file_uploader(
        "Choose an image",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=st.session_state["file_uploader_key"],
    )

    # Display chat messages
    display_chat_messages(uploaded_files)

    # User-provided prompt
    prompt = st.chat_input()

    # Get images from previous messages
    message_images_list = [
        image_id
        for message in st.session_state.messages
        if message["role"] == "user"
        and "images" in message
        and message["images"]
        for image_id in message["images"]
    ]

    # Show image in corresponding chat box
    uploaded_file_ids = []
    if uploaded_files and len(message_images_list) < len(uploaded_files):
        with st.chat_message("user"):
            num_cols = 10
            cols = st.columns(num_cols)
            i = 0
            content_images = []

            for uploaded_file in uploaded_files:
                if uploaded_file.file_id not in message_images_list:
                    uploaded_file_ids.append(uploaded_file.file_id)
                    img = Image.open(uploaded_file)
                    with BytesIO() as output_buffer:
                        img.save(output_buffer, format=img.format)
                        content_image = base64.b64encode(output_buffer.getvalue()).decode(
                            "utf8"
                        )
                    content_images.append(content_image)
                    with cols[i]:
                        st.image(img, caption="", width=75)
                        i += 1
                    if i >= num_cols:
                        i = 0

            if prompt:
                prompt_text = {"type": "text", "text": prompt}
                prompt_new = [prompt_text]
                for content_image in content_images:
                    prompt_image = {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": content_image},
                    }
                    prompt_new.append(prompt_image)
                st.session_state.messages.append(
                    {"role": "user", "content": prompt_new, "images": uploaded_file_ids}
                )
                st.markdown(prompt)

    elif prompt:
        prompt_text = {"type": "text", "text": prompt}
        prompt_new = [prompt_text]
        st.session_state.messages.append({"role": "user", "content": prompt_new})
        with st.chat_message("user"):
            st.markdown(prompt)

    # Modify langchain_messages format
    st.session_state["langchain_messages"] = langchain_messages_format(
        st.session_state["langchain_messages"]
    )

    # Generate a new response if last message is not from assistant
    if st.session_state.messages[-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            response = generate_response(
                conv_chain, [{"role": "user", "content": prompt_new}]
            )
        message = {"role": "assistant", "content": response}
        st.session_state.messages.append(message)


if __name__ == "__main__":
    main()
