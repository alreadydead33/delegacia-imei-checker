import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog, Menu
from PIL import Image, ImageTk
import pandas as pd
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Constantes
API_URL = "https://dash.imei.info/api/check/0/"
CACHE: Dict[str, Dict] = {}  # Cache para armazenar resultados de IMEIs já consultados

# Funções para salvar e carregar a chave da API
def salvar_chave_api(chave: str):
    """Salva a chave da API em um arquivo."""
    with open("api_key.txt", "w") as arquivo:
        arquivo.write(chave)

def carregar_chave_api() -> str:
    """Carrega a chave da API salva em um arquivo."""
    try:
        with open("api_key.txt", "r") as arquivo:
            return arquivo.read().strip()
    except FileNotFoundError:
        return ""  # Retorna uma string vazia se o arquivo não existir

# Model
class IMEModel:
    @staticmethod
    def calcular_digito_verificacao(imei: str) -> int:
        """
        Calcula o dígito de verificação de um IMEI com 14 dígitos usando o algoritmo de Luhn.
        
        :param imei: String com 14 dígitos do IMEI.
        :return: Dígito verificador (0-9).
        """
        if len(imei) != 14:
            raise ValueError("O IMEI deve ter exatamente 14 dígitos.")

        # Passo 1: Dobrar os dígitos alternados (da direita para a esquerda)
        soma = 0
        for i, char in enumerate(imei[::-1]):  # Itera da direita para a esquerda
            digito = int(char)
            if i % 2 == 1:  # Posições ímpares (segundo, quarto, sexto, etc.)
                digito *= 2
                if digito > 9:
                    digito = digito - 9  # Soma dos dígitos se o resultado for maior que 9
            soma += digito

        # Passo 2: Calcular o dígito de verificação
        digito_verificacao = (10 - (soma % 10)) % 10
        return digito_verificacao

    @staticmethod
    async def get_device_info(imei: str, api_key: str) -> Optional[Dict]:
        """Consulta a API para obter informações do dispositivo."""
        if imei in CACHE:
            logging.info(f"Retornando dados do cache para IMEI: {imei}")
            return CACHE[imei]

        url = f"{API_URL}?API_KEY={api_key}&imei={imei}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if data.get('status') == 'Done' and data.get('result'):
                        device_info = {
                            'IMEI': imei,
                            'Marca': data['result'].get('brand'),
                            'Modelo': data['result'].get('model'),
                            'Sistema Operacional': 'Desconhecido'
                        }
                        CACHE[imei] = device_info  # Armazena no cache
                        return device_info
                    else:
                        logging.error(f"Erro na API para IMEI {imei}: {data.get('message')}")
                        return None
        except Exception as e:
            logging.error(f"Erro na requisição para IMEI {imei}: {e}")
            return None

# Controller
class IMEController:
    def __init__(self, view):
        self.view = view
        self.model = IMEModel()

    async def process_imeis(self):
        """Processa a lista de IMEIs e exibe os resultados."""
        api_key = self.view.get_api_key()
        imeis = self.view.get_imeis()

        if not api_key or not imeis:
            self.view.show_error("Por favor, insira a chave da API e pelo menos um IMEI.")
            return

        self.view.clear_results()
        self.view.set_progress_max(len(imeis))

        all_device_info = []
        for imei in imeis:
            if imei.strip():
                try:
                    if not imei.isdigit() or len(imei) not in [14, 15]:
                        raise ValueError("IMEI inválido.")

                    # Se o IMEI tiver 14 dígitos, testa dígitos de 0 a 9
                    if len(imei) == 14:
                        for digito in range(10):  # Testa dígitos de 0 a 9
                            imei_completo = imei + str(digito)
                            device_info = await self.model.get_device_info(imei_completo, api_key)
                            if device_info:
                                all_device_info.append(device_info)
                                self.view.add_result(device_info)
                                break  # Para o loop quando encontrar um IMEI válido
                        else:
                            self.view.show_error(f"Nenhum IMEI válido encontrado para: {imei}")
                    else:
                        # Se o IMEI já tiver 15 dígitos, consulta diretamente
                        device_info = await self.model.get_device_info(imei, api_key)
                        if device_info:
                            all_device_info.append(device_info)
                            self.view.add_result(device_info)

                    self.view.update_progress()
                except ValueError as e:
                    self.view.show_error(f"IMEI inválido: {imei}\nMotivo: {e}")
                except Exception as e:
                    self.view.show_error(f"Erro ao processar IMEI {imei}: {e}")

        if all_device_info:
            self.view.set_export_data(all_device_info)
        else:
            self.view.show_info("Nenhum resultado encontrado.")

# View
class IMEIView:
    def __init__(self, root):
        self.root = root
        self.root.title("Consulta de IMEI")
        self.root.geometry("700x600")

        self.export_data = None  # Dados para exportação
        self.setup_ui()

        # Carrega a última chave da API usada
        self.api_key_entry.insert(0, carregar_chave_api())

    def setup_ui(self):
        """Configura a interface gráfica."""
        # Canvas para a imagem de fundo
        self.canvas = tk.Canvas(self.root, width=700, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        try:
            background_image = Image.open(r"C:\Users\Isaac\Desktop\IMEI_CHECKER\background.png")
            background_image = background_image.resize((700, 600), Image.Resampling.LANCZOS)
            self.background_photo = ImageTk.PhotoImage(background_image)
            self.canvas.create_image(0, 0, image=self.background_photo, anchor=tk.NW)
        except Exception as e:
            logging.error(f"Erro ao carregar a imagem de fundo: {e}")
            self.background_photo = None

        # Frame principal
        self.main_frame = ttk.Frame(self.canvas, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Componentes da interface
        self.setup_api_frame()
        self.setup_imei_frame()
        self.setup_progress_bar()
        self.setup_results_frame()
        self.setup_menu()

    def setup_api_frame(self):
        """Configura o frame da chave da API."""
        api_frame = ttk.Frame(self.main_frame)
        api_frame.pack(fill=tk.X, pady=10)

        api_label = ttk.Label(api_frame, text="Chave da API:")
        api_label.pack(side=tk.LEFT, padx=5)

        self.api_key_entry = ttk.Entry(api_frame, width=50)
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def setup_imei_frame(self):
        """Configura o frame dos IMEIs."""
        imei_frame = ttk.Frame(self.main_frame)
        imei_frame.pack(fill=tk.BOTH, pady=10)

        imei_label = ttk.Label(imei_frame, text="IMEIs (um por linha):")
        imei_label.pack()

        self.imei_text = scrolledtext.ScrolledText(imei_frame, height=10, width=70, font=("Arial", 12))
        self.imei_text.pack()

    def setup_progress_bar(self):
        """Configura a barra de progresso."""
        self.progress = ttk.Progressbar(self.main_frame, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(pady=10)

    def setup_results_frame(self):
        """Configura o frame dos resultados."""
        result_frame = ttk.Frame(self.main_frame)
        result_frame.pack(fill=tk.BOTH, expand=True)

        result_label = ttk.Label(result_frame, text="Resultados:")
        result_label.pack()

        self.result_text = scrolledtext.ScrolledText(result_frame, height=10, width=70, font=("Arial", 12))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # Botão para processar
        process_button = ttk.Button(self.main_frame, text="Consultar IMEIs", command=self.start_processing)
        process_button.pack(pady=20)

    def setup_menu(self):
        """Configura o menu de exportação."""
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Arquivo", menu=file_menu)
        file_menu.add_command(label="Exportar para Excel", command=lambda: self.export_file("excel"))
        file_menu.add_command(label="Exportar para CSV", command=lambda: self.export_file("csv"))
        file_menu.add_command(label="Exportar para TXT", command=lambda: self.export_file("txt"))

    def get_api_key(self) -> str:
        """Retorna a chave da API inserida e a salva."""
        chave = self.api_key_entry.get().strip()
        salvar_chave_api(chave)  # Salva a chave da API
        return chave

    def get_imeis(self) -> List[str]:
        """Retorna a lista de IMEIs inseridos."""
        return self.imei_text.get("1.0", tk.END).strip().splitlines()

    def clear_results(self):
        """Limpa os resultados exibidos."""
        self.result_text.delete(1.0, tk.END)

    def add_result(self, device_info: Dict):
        """Adiciona um resultado à caixa de texto."""
        self.result_text.insert(tk.END, f"IMEI: {device_info['IMEI']}\n")
        self.result_text.insert(tk.END, f"Marca: {device_info['Marca']}\n")
        self.result_text.insert(tk.END, f"Modelo: {device_info['Modelo']}\n")
        self.result_text.insert(tk.END, f"Sistema Operacional: {device_info['Sistema Operacional']}\n")
        self.result_text.insert(tk.END, "-" * 30 + "\n")

    def set_progress_max(self, max_value: int):
        """Define o valor máximo da barra de progresso."""
        self.progress["maximum"] = max_value

    def update_progress(self):
        """Atualiza a barra de progresso."""
        self.progress["value"] += 1
        self.root.update_idletasks()

    def set_export_data(self, data: List[Dict]):
        """Define os dados para exportação."""
        self.export_data = data
        self.show_info("Consulta concluída. Use o menu 'Arquivo' para exportar os resultados.")

    def export_file(self, file_type: str):
        """Exporta os dados para o formato selecionado."""
        if not self.export_data:
            self.show_error("Nenhum dado disponível para exportação.")
            return

        # Define as extensões e filtros para cada tipo de arquivo
        filetypes = {
            "excel": [("Arquivo Excel", "*.xlsx")],
            "csv": [("Arquivo CSV", "*.csv")],
            "txt": [("Arquivo TXT", "*.txt")]
        }

        # Abre o diálogo para salvar o arquivo
        file_path = filedialog.asksaveasfilename(
            defaultextension=f".{file_type}",
            filetypes=filetypes[file_type],
            title=f"Salvar como {file_type.upper()}"
        )

        if file_path:
            df = pd.DataFrame(self.export_data)
            try:
                if file_type == "excel":
                    df.to_excel(file_path, index=False, engine="openpyxl")
                elif file_type == "csv":
                    df.to_csv(file_path, index=False, sep=';')
                elif file_type == "txt":
                    df.to_csv(file_path, index=False, sep='\t')
                self.show_info(f"Arquivo salvo em: {file_path}")
            except Exception as e:
                self.show_error(f"Erro ao salvar o arquivo: {e}")

    def show_error(self, message: str):
        """Exibe uma mensagem de erro."""
        messagebox.showerror("Erro", message)

    def show_info(self, message: str):
        """Exibe uma mensagem informativa."""
        messagebox.showinfo("Info", message)

    def start_processing(self):
        """Inicia o processamento dos IMEIs em uma nova thread assíncrona."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.controller.process_imeis())

# Main
if __name__ == "__main__":
    root = tk.Tk()
    view = IMEIView(root)
    controller = IMEController(view)
    view.controller = controller
    root.mainloop()