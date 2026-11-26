"""Ponto de entrada da interface gráfica."""
import os
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from xml.parsers.expat import ExpatError

import customtkinter as ctk

from src.browser.automation import (
    GDoorSession,
    abrir_consulta_produtos,
    consultar_produtos_no_sistema,
    importar_produtos_no_sistema,
    lancar_no_sistema,
)
from src.nfe.parser import ler_xml_nfe
from src.nfe.xml_storage import (
    copiar_xml_para_notas,
    remover_xml_para_consulta,
)


def obter_pasta_notas():
    pasta_base = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[2]
    )
    return pasta_base / "notasXMLs"


class NFeAutoEntry:

    def __init__(self, root):

        self.root = root
        self.sessao_gdoor = None
        self.consulta_cancelada = threading.Event()
        self.importacao_cancelada = threading.Event()

        self.root.title("NFe Auto Entry")
        self.root.geometry("900x600")
        self.root.minsize(750, 500)

        # Configurações visuais
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Tela inicial de autenticação
        self.criar_tela_login()

    def criar_tela_login(self):
        self.container = ctk.CTkFrame(self.root)
        self.container.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=25
        )

        frame_login = ctk.CTkFrame(self.container)
        frame_login.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            frame_login,
            text="Acesso ao Gdoor",
            font=("Arial", 24, "bold")
        ).pack(pady=(25, 20), padx=40)

        configuracao_email = os.getenv("GDOOR_EMAIL", "")
        configuracao_senha = os.getenv("GDOOR_PASSWORD", "")

        self.campo_email_login = ctk.CTkEntry(
            frame_login,
            width=320,
            height=40,
            placeholder_text="Email"
        )
        self.campo_email_login.insert(0, configuracao_email)
        self.campo_email_login.pack(pady=8)

        self.campo_senha_login = ctk.CTkEntry(
            frame_login,
            width=320,
            height=40,
            placeholder_text="Senha",
            show="*"
        )
        self.campo_senha_login.insert(0, configuracao_senha)
        self.campo_senha_login.pack(pady=8)

        self.mensagem_login = ctk.CTkLabel(
            frame_login,
            text=""
        )
        self.mensagem_login.pack(pady=(8, 0))

        self.btn_abrir_gdoor = ctk.CTkButton(
            frame_login,
            text="Abrir Gdoor",
            width=320,
            height=45,
            command=self.abrir_gdoor
        )
        self.btn_abrir_gdoor.pack(pady=(15, 25))

    def limpar_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def abrir_gdoor(self):
        email = self.campo_email_login.get().strip()
        senha = self.campo_senha_login.get()

        if not email or not senha:
            self.mensagem_login.configure(
                text="Informe o email e a senha."
            )
            return

        self.btn_abrir_gdoor.configure(
            state="disabled",
            text="Abrindo Gdoor..."
        )
        self.mensagem_login.configure(text="")

        threading.Thread(
            target=self.executar_abertura_gdoor,
            args=(email, senha),
            daemon=True
        ).start()

    def executar_abertura_gdoor(self, email, senha):
        try:
            self.sessao_gdoor = GDoorSession(
                email,
                senha
            )
            self.sessao_gdoor.abrir()
            self.root.after(0, self.criar_interface)
        except Exception as exc:
            mensagem_erro = str(exc)
            self.root.after(
                0,
                lambda: self.mostrar_erro_login(mensagem_erro)
            )

    def mostrar_erro_login(self, mensagem):
        self.mensagem_login.configure(
            text=f"Falha ao abrir o Gdoor: {mensagem}"
        )
        self.btn_abrir_gdoor.configure(
            state="normal",
            text="Abrir Gdoor"
        )

    def criar_interface(self):

        if hasattr(self, "container"):
            self.container.destroy()

        # Container principal
        self.container = ctk.CTkFrame(self.root)
        self.container.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=25
        )

        # Título
        self.titulo = ctk.CTkLabel(
            self.container,
            text="NFe Auto Entry",
            font=("Arial", 26, "bold")
        )

        self.titulo.pack(pady=(20, 5))

        self.subtitulo = ctk.CTkLabel(
            self.container,
            text="Selecione uma operação"
        )

        self.subtitulo.pack(pady=(0, 25))

        # Área das opções
        self.opcoes = ctk.CTkFrame(
            self.container,
            fg_color="transparent"
        )

        self.opcoes.pack(fill="x", padx=25)

        self.btn_produtos = ctk.CTkButton(
            self.opcoes,
            text="Consultar produtos",
            height=50,
            command=self.selecionar_produtos
        )

        self.btn_produtos.pack(
            side="left",
            expand=True,
            fill="x",
            padx=10
        )
        self.btn_importar_produtos = ctk.CTkButton(
            self.opcoes,
            text="Cadastrar produtos",
            height=50,
            command=self.selecionar_cadastro_produtos
        )
        self.btn_importar_produtos.pack(
            side="left",
            expand=True,
            fill="x",
            padx=10
        )

        self.btn_notas = ctk.CTkButton(
            self.opcoes,
            text="Importar nota",
            height=50,
            command=self.selecionar_nota
        )

        self.btn_notas.pack(
            side="left",
            expand=True,
            fill="x",
            padx=10
        )

        # Área de conteúdo
        self.conteudo = ctk.CTkFrame(self.container)
        self.conteudo.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=25
        )

        self.selecionar_produtos()

    def selecionar_cadastro_produtos(self):
        self.limpar_conteudo()
        self.caminho_xml_cadastro = None

        ctk.CTkLabel(
            self.conteudo,
            text="Cadastro de produtos",
            font=("Arial", 20, "bold"),
        ).pack(pady=(20, 5))
        ctk.CTkLabel(
            self.conteudo,
            text="Selecione um XML e inicie o cadastro no GDOOR.",
        ).pack(pady=(0, 15))

        botoes_cadastro = ctk.CTkFrame(
            self.conteudo,
            fg_color="transparent",
        )
        botoes_cadastro.pack(pady=5)

        self.btn_selecionar_xml_cadastro = ctk.CTkButton(
            botoes_cadastro,
            text="Selecionar XML",
            command=self.selecionar_xml_cadastro,
        )
        self.btn_selecionar_xml_cadastro.pack(side="left", padx=5)

        self.btn_iniciar_cadastro = ctk.CTkButton(
            botoes_cadastro,
            text="Iniciar cadastro",
            command=self.iniciar_importacao_produtos,
            state="disabled",
        )
        self.btn_iniciar_cadastro.pack(side="left", padx=5)

        self.btn_parar_cadastro = ctk.CTkButton(
            botoes_cadastro,
            text="Parar cadastro",
            fg_color="#C62828",
            hover_color="#A31616",
            command=self.parar_importacao_produtos,
            state="disabled",
        )
        self.btn_parar_cadastro.pack(side="left", padx=5)

        self.label_xml_cadastro = ctk.CTkLabel(
            self.conteudo,
            text="Nenhum XML selecionado.",
        )
        self.label_xml_cadastro.pack(pady=(5, 10))

        self.barra_progresso_cadastro = ctk.CTkProgressBar(
            self.conteudo,
            width=650,
        )
        self.barra_progresso_cadastro.set(0)
        self.barra_progresso_cadastro.pack(
            padx=20,
            pady=(5, 0),
            fill="x",
        )
        self.status_cadastro = ctk.CTkLabel(
            self.conteudo,
            text="Aguardando XML.",
        )
        self.status_cadastro.pack(pady=(0, 8))

        self.lista_cadastro = ctk.CTkTextbox(
            self.conteudo,
            width=650,
            height=250,
        )
        self.lista_cadastro.pack(
            padx=20,
            pady=(5, 10),
            fill="both",
            expand=True,
        )

    def selecionar_xml_cadastro(self):
        caminho_arquivo = filedialog.askopenfilename(
            parent=self.root,
            title="Selecione o XML dos produtos",
            filetypes=[("Arquivos XML", "*.xml"), ("Todos os arquivos", "*.*")]
        )
        if not caminho_arquivo:
            return

        self.caminho_xml_cadastro = Path(caminho_arquivo)
        self.label_xml_cadastro.configure(
            text=f"XML selecionado: {self.caminho_xml_cadastro.name}"
        )
        self.status_cadastro.configure(text="Pronto para iniciar o cadastro.")
        self.barra_progresso_cadastro.set(0)
        self.lista_cadastro.delete("1.0", "end")
        self.btn_iniciar_cadastro.configure(state="normal")

    def iniciar_importacao_produtos(self):
        if not self.sessao_gdoor or not self.sessao_gdoor.page:
            self.mostrar_aviso_sessao()
            return

        caminho_arquivo = self.caminho_xml_cadastro
        if not caminho_arquivo or not caminho_arquivo.is_file():
            messagebox.showerror(
                "XML não encontrado",
                "Selecione um arquivo XML válido antes de iniciar.",
                parent=self.root,
            )
            return

        self.importacao_cancelada.clear()
        self.btn_selecionar_xml_cadastro.configure(state="disabled")
        self.btn_iniciar_cadastro.configure(state="disabled")
        self.btn_parar_cadastro.configure(
            state="normal",
            text="Parar cadastro",
        )
        self.barra_progresso_cadastro.set(0)
        self.status_cadastro.configure(text="Preparando cadastro...")
        self.lista_cadastro.delete("1.0", "end")
        self.btn_importar_produtos.configure(
            state="disabled",
            text="Cadastrando..."
        )
        self.btn_produtos.configure(state="disabled")
        self.btn_notas.configure(state="disabled")
        threading.Thread(
            target=self.executar_importacao_produtos,
            args=(caminho_arquivo,),
            daemon=True
        ).start()

    def parar_importacao_produtos(self):
        self.importacao_cancelada.set()
        self.btn_parar_cadastro.configure(
            state="disabled",
            text="Parando após o produto atual...",
        )
        self.status_cadastro.configure(
            text="O cadastro será interrompido após o produto atual."
        )

    def executar_importacao_produtos(self, caminho_arquivo):
        try:
            self.total_cadastro = 0

            def informar_progresso(indice, total, produto, estado):
                if estado == "preparando":
                    self.total_cadastro = total
                self.root.after(
                    0,
                    lambda i=indice, t=total, p=produto, s=estado: (
                        self.atualizar_progresso_cadastro(
                            i,
                            t,
                            p,
                            s,
                        )
                    ),
                )

            produtos = self.sessao_gdoor.executar(
                importar_produtos_no_sistema,
                caminho_arquivo,
                aguardar=False,
                progress_callback=informar_progresso,
                stop_event=self.importacao_cancelada,
            )
            produtos = produtos or []
            if (
                self.importacao_cancelada.is_set()
                and len(produtos) < self.total_cadastro
            ):
                mensagem = (
                    f"Cadastro interrompido: {len(produtos)}/"
                    f"{self.total_cadastro} produto(s) enviado(s) ao GDOOR."
                )
            elif not produtos:
                mensagem = "O XML não contém produtos para cadastrar."
            else:
                mensagem = (
                    f"{len(produtos)} produto(s) enviado(s) ao GDOOR "
                    "para salvar. Confira os cadastros no sistema."
                )
            erro = False
        except Exception as exc:
            mensagem = f"Erro ao processar o XML: {exc}"
            erro = True

        self.root.after(
            0,
            lambda texto=mensagem, falhou=erro: (
                self.finalizar_importacao_produtos(texto, falhou)
            )
        )

    def finalizar_importacao_produtos(self, mensagem, erro):
        self.btn_importar_produtos.configure(
            state="normal",
            text="Cadastrar produtos"
        )
        self.btn_selecionar_xml_cadastro.configure(state="normal")
        self.btn_iniciar_cadastro.configure(
            state=(
                "normal"
                if self.caminho_xml_cadastro
                and self.caminho_xml_cadastro.is_file()
                else "disabled"
            )
        )
        self.btn_produtos.configure(state="normal")
        self.btn_notas.configure(state="normal")
        self.btn_parar_cadastro.configure(
            state="disabled",
            text="Parar cadastro",
        )
        self.status_cadastro.configure(text=mensagem)
        self.lista_cadastro.insert("end", f"\n{mensagem}\n")
        self.lista_cadastro.see("end")
        if erro:
            messagebox.showerror("Falha no processamento", mensagem)
        else:
            messagebox.showinfo("Processamento concluído", mensagem)

    def atualizar_progresso_cadastro(
        self,
        indice,
        total,
        produto,
        estado,
    ):
        progresso = indice / total if total else 0
        if estado == "preparando":
            self.status_cadastro.configure(
                text=f"0/{total} produtos enviados ao GDOOR"
            )
            return

        if estado == "interrompido":
            self.barra_progresso_cadastro.set(progresso)
            self.status_cadastro.configure(
                text=f"Cadastro interrompido: {indice}/{total} enviados"
            )
            self.lista_cadastro.insert(
                "end",
                f"Cadastro interrompido após {indice}/{total} produto(s).\n",
            )
            self.lista_cadastro.see("end")
            return

        nome_produto = f"{produto['codigo']} - {produto['nome']}"
        if estado == "processando":
            self.status_cadastro.configure(
                text=(
                    f"Processando {indice}/{total} | "
                    f"{indice - 1} enviado(s)"
                )
            )
            self.lista_cadastro.insert(
                "end",
                f"Processando {indice}/{total}: {nome_produto}\n",
            )
        elif estado == "enviado":
            self.barra_progresso_cadastro.set(progresso)
            self.status_cadastro.configure(
                text=f"{indice}/{total} produtos enviados ao GDOOR"
            )
            self.lista_cadastro.insert(
                "end",
                f"Salvamento enviado ao GDOOR: {nome_produto}\n",
            )
        elif estado == "erro":
            self.status_cadastro.configure(
                text=f"Falha no produto {indice}/{total}"
            )
            self.lista_cadastro.insert(
                "end",
                f"Falha ao processar {indice}/{total}: {nome_produto}\n",
            )
        self.lista_cadastro.see("end")

    def selecionar_produtos(self):

        self.limpar_conteudo()

        titulo = ctk.CTkLabel(
            self.conteudo,
            text="Consulte produtos do sistema",
            font=("Arial", 20, "bold")
        )

        titulo.pack(pady=30)

        descricao = ctk.CTkLabel(
            self.conteudo,
            text=(
                "Adicione um XML e consulte quais produtos "
                "já existem no sistema."
            ),
        )

        descricao.pack(pady=10)

        botoes_produtos = ctk.CTkFrame(
            self.conteudo,
            fg_color="transparent"
        )
        botoes_produtos.pack(pady=15)

        self.btn_adicionar_xml = ctk.CTkButton(
            botoes_produtos,
            text="Selecionar XML para consulta",
            height=40,
            command=self.adicionar_xml_notas,
        )
        self.btn_adicionar_xml.pack(side="left", padx=(0, 8))

        self.btn_remover_xml = ctk.CTkButton(
            botoes_produtos,
            text="Remover XML",
            height=40,
            command=self.gerenciar_xml_notas,
        )
        self.btn_remover_xml.pack(side="left", padx=(0, 8))

        self.btn_abrir_consulta = ctk.CTkButton(
            botoes_produtos,
            text="Parar consulta",
            height=40,
            fg_color="#C62828",
            hover_color="#A31616",
            command=self.parar_consulta,
            state="disabled"
        )
        self.btn_abrir_consulta.pack(
            side="left",
            padx=(0, 8)
        )

        self.btn_consultar = ctk.CTkButton(
            botoes_produtos,
            text="Consultar produtos no sistema",
            height=40,
            command=self.iniciar_consulta_produtos
        )
        self.btn_consultar.pack(side="left")

        self.barra_progresso_consulta = ctk.CTkProgressBar(
            self.conteudo,
            width=650,
        )
        self.barra_progresso_consulta.set(0)
        self.barra_progresso_consulta.pack(
            padx=20,
            pady=(5, 0),
            fill="x",
        )

        self.label_progresso_consulta = ctk.CTkLabel(
            self.conteudo,
            text="Consultados: 0/0 | Faltantes: 0",
        )
        self.label_progresso_consulta.pack(pady=(0, 5))

        self.resultado_consulta = ctk.CTkTextbox(
            self.conteudo,
            width=650,
            height=280
        )
        self.resultado_consulta._textbox.tag_config(
            "existente",
            foreground="#2ECC71",
            font=("Arial", 13, "bold")
        )
        self.resultado_consulta._textbox.tag_config(
            "inexistente",
            foreground="#E74C3C",
            font=("Arial", 13, "bold")
        )
        self.resultado_consulta.pack(
            padx=20,
            pady=(5, 20),
            fill="both",
            expand=True
        )

    def adicionar_xml_notas(self):
        caminho_origem = filedialog.askopenfilename(
            parent=self.root,
            title="Selecione um XML de NF-e",
            filetypes=[("Arquivos XML", "*.xml")],
        )
        if not caminho_origem:
            return

        try:
            destino, copiado = copiar_xml_para_notas(
                caminho_origem,
                obter_pasta_notas(),
            )
        except (
            AttributeError,
            ExpatError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            messagebox.showerror(
                "Falha ao adicionar XML",
                f"Não foi possível adicionar o arquivo:\n{exc}",
                parent=self.root,
            )
            return

        if copiado:
            mensagem = (
                f"XML {destino.name} validado e pronto para consulta."
            )
        else:
            mensagem = f"XML {destino.name} já está pronto para consulta."
        messagebox.showinfo(
            "XML pronto para consulta",
            mensagem,
            parent=self.root,
        )
        self.resultado_consulta.insert(
            "end",
            f"XML disponível para consulta: {destino.name}\n",
        )

    def gerenciar_xml_notas(self):
        pasta_notas = obter_pasta_notas()
        arquivos = sorted(
            (arquivo for arquivo in pasta_notas.glob("*.xml") if arquivo.is_file()),
            key=lambda arquivo: arquivo.name.casefold(),
        )
        if not arquivos:
            messagebox.showinfo(
                "Nenhum XML",
                "Não há XMLs adicionados para remover.",
                parent=self.root,
            )
            return

        janela = ctk.CTkToplevel(self.root)
        janela.title("Remover XML da consulta")
        janela.geometry("520x420")
        janela.transient(self.root)
        janela.grab_set()

        ctk.CTkLabel(
            janela,
            text="Selecione o XML que deseja remover da consulta.",
            font=("Arial", 16, "bold"),
        ).pack(padx=20, pady=(20, 10))

        lista_xml = ctk.CTkScrollableFrame(janela, height=280)
        lista_xml.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            janela,
            text="A remoção apaga somente a cópia usada pelo aplicativo.",
        ).pack(padx=20, pady=(0, 15))

        def atualizar_lista():
            for widget in lista_xml.winfo_children():
                widget.destroy()

            arquivos_atuais = sorted(
                (
                    arquivo
                    for arquivo in pasta_notas.glob("*.xml")
                    if arquivo.is_file()
                ),
                key=lambda arquivo: arquivo.name.casefold(),
            )
            if not arquivos_atuais:
                ctk.CTkLabel(
                    lista_xml,
                    text="Não há XMLs adicionados.",
                ).pack(padx=10, pady=15)
                return

            for arquivo in arquivos_atuais:
                linha = ctk.CTkFrame(lista_xml)
                linha.pack(fill="x", padx=5, pady=4)
                ctk.CTkLabel(
                    linha,
                    text=arquivo.name,
                    anchor="w",
                ).pack(side="left", fill="x", expand=True, padx=10, pady=8)
                ctk.CTkButton(
                    linha,
                    text="Remover",
                    width=90,
                    fg_color="#C62828",
                    hover_color="#A31616",
                    command=lambda item=arquivo: remover_xml(item),
                ).pack(side="right", padx=8, pady=5)

        def remover_xml(arquivo):
            confirmar = messagebox.askyesno(
                "Confirmar remoção",
                f"Remover {arquivo.name} da consulta?\n"
                "O arquivo original não será apagado.",
                parent=janela,
            )
            if not confirmar:
                return

            try:
                remover_xml_para_consulta(arquivo, pasta_notas)
            except (OSError, ValueError) as exc:
                messagebox.showerror(
                    "Falha ao remover XML",
                    f"Não foi possível remover o XML:\n{exc}",
                    parent=janela,
                )
                return

            self.resultado_consulta.insert(
                "end",
                f"XML removido da consulta: {arquivo.name}\n",
            )
            atualizar_lista()

        atualizar_lista()

    def parar_consulta(self):
        self.consulta_cancelada.set()
        self.btn_abrir_consulta.configure(
            state="disabled",
            text="Parando..."
        )

    def iniciar_consulta_produtos(self):
        self.consulta_cancelada.clear()
        self.btn_adicionar_xml.configure(state="disabled")
        self.btn_remover_xml.configure(state="disabled")
        self.barra_progresso_consulta.set(0)
        self.label_progresso_consulta.configure(
            text="Preparando consulta..."
        )
        self.btn_consultar.configure(
            state="disabled",
            text="Consultando..."
        )
        self.btn_abrir_consulta.configure(
            state="normal",
            text="Parar consulta"
        )
        self.resultado_consulta.delete("1.0", "end")

        threading.Thread(
            target=self.executar_consulta_produtos,
            daemon=True
        ).start()

    def executar_consulta_produtos(self):
        if not self.sessao_gdoor or not self.sessao_gdoor.page:
            self.root.after(
                0,
                lambda: self.atualizar_resultado(
                    "Abra o Gdoor antes de consultar.",
                    finalizar=True
                )
            )
            return

        pasta_xml = obter_pasta_notas()
        arquivos_xml = sorted(pasta_xml.glob("*.xml"))

        if not arquivos_xml:
            self.root.after(
                0,
                lambda: self.atualizar_resultado(
                    "Nenhum XML selecionado. Use o botão "
                    "'Selecionar XML para consulta' antes de iniciar.",
                    finalizar=True
                )
            )
            return

        try:
            resultados = self.sessao_gdoor.executar(
                consultar_produtos_no_sistema,
                arquivos_xml,
                stop_event=self.consulta_cancelada,
                callback=lambda resultado: self.root.after(
                    0,
                    lambda item=resultado: (
                        self.atualizar_resultado(
                            item["texto"],
                            existe=item["existe"]
                        )
                    )
                ),
                progress_callback=lambda consultados, total, faltantes: (
                    self.root.after(
                        0,
                        lambda c=consultados, t=total, f=faltantes: (
                            self.atualizar_progresso_consulta(c, t, f)
                        ),
                    )
                ),
            )
            existentes = sum(1 for item in resultados if item["existe"])
            faltantes = len(resultados) - existentes
            estado = (
                "Consulta interrompida"
                if self.consulta_cancelada.is_set()
                else "Consulta concluída"
            )
            resumo = (
                f"\n{estado}: {len(resultados)} consultado(s), "
                f"{existentes} existente(s) e {faltantes} faltante(s)."
            )
            self.root.after(
                0,
                lambda: self.finalizar_consulta(resumo)
            )
        except Exception as exc:
            mensagem_erro = f"Erro na consulta: {exc}"
            self.root.after(
                0,
                lambda: self.finalizar_consulta(mensagem_erro)
            )

    def atualizar_progresso_consulta(self, consultados, total, faltantes):
        progresso = consultados / total if total else 0
        self.barra_progresso_consulta.set(progresso)
        self.label_progresso_consulta.configure(
            text=(
                f"Consultados: {consultados}/{total} | "
                f"Faltantes: {faltantes}"
            )
        )

    def atualizar_resultado(self, texto, finalizar=False, existe=None):
        if existe is not None:
            marcacao = "EXISTE" if existe else "NÃO EXISTE"
            simbolo = "●"
            inicio = self.resultado_consulta._textbox.index("end-1c")
            self.resultado_consulta.insert(
                "end",
                f"{simbolo} {marcacao}"
            )
            fim = self.resultado_consulta._textbox.index("end-1c")
            self.resultado_consulta._textbox.tag_add(
                "existente" if existe else "inexistente",
                inicio,
                fim
            )

            inicio_texto = texto.find(" - ")
            if inicio_texto >= 0:
                prefixo = (
                    texto[:inicio_texto]
                    .replace("EXISTE", "")
                    .replace("NÃO EXISTE", "")
                    .strip()
                )
                criterio = texto[inicio_texto + 3:]
                detalhe = f" {prefixo} - {criterio}"
            else:
                detalhe = f" {texto}"
            self.resultado_consulta.insert("end", f"{detalhe}\n")
        else:
            self.resultado_consulta.insert("end", texto + "\n")
        self.resultado_consulta.see("end")

        if finalizar:
            self.btn_adicionar_xml.configure(state="normal")
            self.btn_remover_xml.configure(state="normal")
            self.btn_consultar.configure(
                state="normal",
                text="Consultar produtos no sistema"
            )
            self.btn_abrir_consulta.configure(
                state="disabled",
                text="Parar consulta"
            )

    def finalizar_consulta(self, texto):
        self.atualizar_resultado(texto, finalizar=True)
        self.btn_abrir_consulta.configure(
            state="disabled",
            text="Parar consulta"
        )

    def selecionar_nota(self):

        self.limpar_conteudo()

        titulo = ctk.CTkLabel(
            self.conteudo,
            text="Importação de nota fiscal",
            font=("Arial", 20, "bold")
        )

        titulo.pack(pady=20)

        self.campo_id = ctk.CTkEntry(
            self.conteudo,
            placeholder_text="Digite o ID da nota",
            width=300,
            height=40
        )

        self.campo_id.pack(pady=15)

        self.checkbox_ibscbs = ctk.CTkCheckBox(
            self.conteudo,
            text="Importar IBS/CBS",
            command=self.alternar_ibscbs
        )

        self.checkbox_ibscbs.pack(pady=15)

        self.campos_adicionais = ctk.CTkFrame(
            self.conteudo,
            fg_color="transparent"
        )

        self.status_importacao = ctk.CTkLabel(
            self.conteudo,
            text="",
            wraplength=650
        )
        self.status_importacao.pack(pady=(5, 0))

        self.btn_iniciar = ctk.CTkButton(
            self.conteudo,
            text="Iniciar importação",
            height=40,
            command=self.iniciar_importacao
        )

        self.btn_iniciar.pack(pady=25)

    def alternar_ibscbs(self):

        if self.checkbox_ibscbs.get():

            self.campos_adicionais.pack(pady=15)

            # Campos adicionais serão implementados aqui.

        else:

            self.campos_adicionais.pack_forget()

    def limpar_conteudo(self):

        for widget in self.conteudo.winfo_children():
            widget.destroy()

    def iniciar_importacao(self):
        if not self.sessao_gdoor or not self.sessao_gdoor.page:
            self.mostrar_aviso_sessao()
            return

        id_nota = self.campo_id.get().strip()
        if not id_nota:
            return

        arquivos_xml = sorted(obter_pasta_notas().glob("*.xml"))
        if not arquivos_xml:
            return

        importar_ibscbs = bool(self.checkbox_ibscbs.get())
        self.status_importacao.configure(text="Importando nota...")
        self.btn_iniciar.configure(
            state="disabled",
            text="Importando...",
            command=self.iniciar_importacao
        )
        self.btn_produtos.configure(state="disabled")
        self.btn_notas.configure(state="disabled")
        threading.Thread(
            target=self.executar_importacao_nota,
            args=(id_nota, arquivos_xml, importar_ibscbs),
            daemon=True
        ).start()

    def aguardar_selecao_manual(self, produto):
        evento = threading.Event()
        self.evento_continuar_importacao = evento
        mensagem = (
            "Produto não encontrado automaticamente: "
            f"{produto['codigo']} - {produto['nome']}. "
            "Selecione-o manualmente na janela do Gdoor e clique "
            "em continuar."
        )
        self.root.after(
            0,
            lambda: self.solicitar_selecao_manual(mensagem)
        )
        evento.wait()
        self.evento_continuar_importacao = None

    def solicitar_selecao_manual(self, mensagem):
        self.status_importacao.configure(
            text=mensagem,
            text_color="#E74C3C"
        )
        self.btn_iniciar.configure(
            state="normal",
            text="Continuar",
            command=self.continuar_importacao_manual
        )

    def continuar_importacao_manual(self):
        evento = getattr(self, "evento_continuar_importacao", None)
        if evento is None:
            return
        self.status_importacao.configure(
            text="Seleção confirmada. Continuando a importação...",
            text_color=("gray10", "#DCE4EE")
        )
        self.btn_iniciar.configure(
            state="disabled",
            text="Importando...",
            command=self.iniciar_importacao
        )
        evento.set()

    def executar_importacao_nota(
        self,
        id_nota,
        arquivos_xml,
        importar_ibscbs=False,
    ):
        try:
            for arquivo in arquivos_xml:
                dados_nota = ler_xml_nfe(arquivo)
                self.sessao_gdoor.executar(
                    lancar_no_sistema,
                    dados_nota,
                    id_nota=id_nota,
                    aguardar_selecao_manual=self.aguardar_selecao_manual,
                    importar_ibscbs=importar_ibscbs,
                )
            mensagem = "Importação concluída. Confira os dados no Gdoor."
        except Exception as exc:
            mensagem = f"Erro na importação: {exc}"
        finally:
            self.root.after(
                0,
                lambda: self.finalizar_importacao(mensagem)
            )

    def finalizar_importacao(self, mensagem):
        self.status_importacao.configure(
            text=mensagem,
            text_color=("gray10", "#DCE4EE")
        )
        self.btn_iniciar.configure(
            state="normal",
            text="Iniciar importação",
            command=self.iniciar_importacao
        )
        self.btn_produtos.configure(state="normal")
        self.btn_notas.configure(state="normal")

    def mostrar_aviso_sessao(self):
        print("Abra o Gdoor antes de iniciar uma operação.")
