"""Ponto de entrada da interface gráfica."""
import os
import sys
import threading
from pathlib import Path

import customtkinter as ctk

from src.browser.automation import (
    GDoorSession,
    abrir_consulta_produtos,
    consultar_produtos_no_sistema,
    importar_produtos_no_sistema,
    lancar_no_sistema,
)
from src.nfe.parser import ler_xml_nfe


class NFeAutoEntry:

    def __init__(self, root):

        self.root = root
        self.sessao_gdoor = None
        self.consulta_cancelada = threading.Event()

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
            text="Importar produtos",
            height=50,
            command=self.selecionar_produtos
        )

        self.btn_produtos.pack(
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

    def selecionar_produtos(self):

        self.limpar_conteudo()

        titulo = ctk.CTkLabel(
            self.conteudo,
            text="Importação de produtos",
            font=("Arial", 20, "bold")
        )

        titulo.pack(pady=30)

        descricao = ctk.CTkLabel(
            self.conteudo,
            text="Consulte os produtos dos XMLs da pasta notasXMLs."
        )

        descricao.pack(pady=10)

        botoes_produtos = ctk.CTkFrame(
            self.conteudo,
            fg_color="transparent"
        )
        botoes_produtos.pack(pady=15)

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

    def parar_consulta(self):
        self.consulta_cancelada.set()
        self.btn_abrir_consulta.configure(
            state="disabled",
            text="Parando..."
        )

    def iniciar_consulta_produtos(self):
        self.consulta_cancelada.clear()
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

        if getattr(sys, "frozen", False):
            pasta_base = Path(os.path.dirname(sys.executable))
        else:
            pasta_base = Path(__file__).resolve().parents[2]

        pasta_xml = pasta_base / "notasXMLs"
        arquivos_xml = sorted(pasta_xml.glob("*.xml"))

        if not arquivos_xml:
            self.root.after(
                0,
                lambda: self.atualizar_resultado(
                    f"Nenhum XML encontrado em: {pasta_xml}",
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
                )
            )
            existentes = sum(1 for item in resultados if item["existe"])
            resumo = (
                f"\nConsulta concluida: {existentes} existente(s) "
                f"e {len(resultados) - existentes} não existente(s)."
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

        pasta_base = (
            Path(os.path.dirname(sys.executable))
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2]
        )
        arquivos_xml = sorted((pasta_base / "notasXMLs").glob("*.xml"))
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
