# bibliotecas necessárias para trabalhar com o bot do Telegram

from telegram import Update                 # atualizar bot com as mensagens
from telegram.ext import CallbackContext    # definir o contexto da mensagem
from telegram.ext import ContextTypes       # definir o tipo de contexto
from telegram.ext import ApplicationBuilder # criar a aplicação de conexão com o bot
from telegram.ext import CommandHandler     # criar um comando para o bot
from telegram.ext import MessageHandler     # criar um manipulador de mensagens
from telegram.ext import filters            # aplicar filtros nas mensagens 

# bibliotecas necessárias para trabalhar com os arquivos pdf

import os                               # para trabalhar com os caminhos das pastas
from langchain.embeddings import OpenAIEmbeddings # converter texto -> número/vetor
from langchain.vectorstores import Chroma                 # criar BD
from langchain.chains import ConversationalRetrievalChain # definir MRI
from langchain.memory import ConversationBufferMemory     # memória do MRI
from langchain.llms import OpenAI                         # usar modelo GPT
from langchain.callbacks import get_openai_callback       # recuperar custo de uso
from langchain.document_loaders import PyPDFDirectoryLoader # ler arquivos PDF
from langchain.text_splitter import CharacterTextSplitter   # dividir pdfs
from deep_translator import GoogleTranslator                # traduzir resposta

modelo_treinado = None      # variável global, armazenar o MRI
pdfs_carregados = False     # variável global, verificar carregamento dos pdf
custo_total = 0             # variável global, armazenar custo total de uso
chave_bot = "SUA CHAVE AQUI"  # chave bot Telegram
chave_gpt = "SUA CHAVE AQUI"  #chave API OpenAI
nome_modelo = "gpt-3.5-turbo-16k" # mudar de acordo com o modelo da chave

# Função para dividir todo o texto dos PDFs em pedaços menores

def dividir_docs(texto):
    # Divisor (tamanho do bloco, 1000 tokens e sobreposição de 200 tokens)
    divisor_texto = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    # Divide o documento em pedaços
    textos = divisor_texto.split_documents(texto)
    return textos

# Função para carregar o modelo de linguagem e o banco de dados

def ler_pdfs():
    global modelo_treinado  # Chamando a variável global para dentro da função
    global chave_gpt            
    os.environ["OPENAI_API_KEY"] = chave_gpt # Define chave como variável ambiente

    print("\n--> Carregando arquivos PDF!\n")

    loader = PyPDFDirectoryLoader("/base_pdfs") # Identif. PDFs na pasta
    pdfs = loader.load()                # Carrega os arquivos pdf
    pdfs = dividir_docs(pdfs)           # dividir pdfs em pedaços menores de tokens
    
    embeddings = OpenAIEmbeddings() # Carrega motor conversão (texto->vetores/num)

    vectordb = Chroma.from_documents(pdfs,
                                     embedding=embeddings,
                                     persist_directory="./base_vetorizada")
    
    vectordb.persist()               # Salva o banco de dados em disco
    
    print("\n--> Banco de dados criado com sucesso!\n")

    memoria = ConversationBufferMemory(memory_key="chat_history",
                                       return_messages=True) # Cria memória do MRI

    modelo_treinado = ConversationalRetrievalChain.from_llm(
            OpenAI(temperature=0.3, # entre 0 e 1, menos e mais criativo
                   model_name=nome_modelo),
            vectordb.as_retriever(), # Converte o banco de dados para um MRI
            memory=memoria,
            chain_type="stuff") #para responder perguntas de forma direta

    print("\n--> Modelo de recuperação conversacional criado com sucesso!\n")

def traduzir_resposta(texto):
    tradutor = GoogleTranslator(source="en", target="pt")
    texto_traduzido = tradutor.translate(texto)
    return texto_traduzido

# Função para escrever a mensagem de boas vindas
# "async def": Função assíncrona, recebe dois parâmetros (update e context) e não retorna nada (-> None)
async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # "await": serve para esperar a mensagem ser enviada
    # "update.message.reply_text": envia uma mensagem de texto para o usuário
    await update.message.reply_text(f'Oi {update.effective_user.first_name}')
    # Mensagem de apresentação
    await update.message.reply_text(f'Posso lhe responder dúvidas sobre Saneamento Básico, baseado no Manual de Saneamento da FUNASA!')
    await update.message.reply_text(f'Qual a sua dúvida?')
    #
    #
    
# Função para responder às perguntas dos usuários
async def responder_pergunta(update: Update, context: CallbackContext) -> None:
    # Captura a mensagem enviada pelo usuário
    mensagem_usuario = update.message.text.lower() # Converte para letras minúsculas

    if modelo_treinado is not None: # Verifica se o MRI já foi carregado

        # Gerenciamento do uso da API
        # "with": serve para abrir o manipulador de retornos de chamadas da OpenAI
        with get_openai_callback() as cb:
            # Faz a pergunta para o MRI
            resultado = modelo_treinado({"question": mensagem_usuario}) 
            
            print(f'{cb}\n')     # Imprime o custo da requisição atual

        resposta = traduzir_resposta(resultado["answer"])  # Traduz a resposta

        # Somar cb.total_cost para saber o custo total durante a conversa (gerenciamento do uso da API)
        global custo_total
        custo_total += cb.total_cost
    
    # Envia a resposta no Telegram para o usuário
    await update.message.reply_text(resposta)

# Função de encerramento da conversa
async def encerrar_conversa(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f'Foi um prazer conversar com você!')
    await update.message.reply_text(f'Até mais!')
    
    # Imprimir o custo total da conversa (gerenciamento do uso da API)
    print(f'\nO custo total da conversa foi de $ {custo_total}.\n')


if not pdfs_carregados:     # Verifica se os arquivos pdf já foram carregados
    ler_pdfs()              # Executa a função para carregar o MRI e o BD
    pdfs_carregados = True  # Para não carregar novamente os arquivos pdf

# Criar aplicação que vai fazer a conexão com o bot
bot = ApplicationBuilder().token(chave_bot).build()

# Adicionar o comando de inicialização do conversa ao bot (/start)
bot.add_handler(CommandHandler("start", boas_vindas))

# Adicionar um manipulador de mensagens para responder às perguntas do usuário
# filters.TEXT: para capturar apenas mensagens de texto
# (~ filters.COMMAND): para não capturar comandos
bot.add_handler(MessageHandler(filters.TEXT & (~ filters.COMMAND), responder_pergunta))

# Adicionar o comando de encerramento da conversa ao bot (/encerrar)
bot.add_handler(CommandHandler("stop", encerrar_conversa))

# Iniciar o bot em modo de polling (esperando mensagens)
bot.run_polling()