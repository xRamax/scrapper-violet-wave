import gspread
import pandas as pd
import re
import json
import os
from google.oauth2.service_account import Credentials
from app.core.config import settings

class GSheetService:
    def __init__(self, spreadsheet_id=None):
        """
        Conecta a Google Sheets usando archivo físico O variable de entorno (Nube).
        """
        # Definimos los permisos necesarios
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = None
        
        # 1. Intentar cargar desde Variable de Entorno (Railway/Nube)
        # Esto permite pegar el contenido del JSON en una variable sin subir el archivo
        if settings.GOOGLE_CREDENTIALS_JSON:
            try:
                # print("[INFO] Usando credenciales desde Variable de Entorno (JSON).") 
                creds_dict = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            except Exception as e:
                print(f"[ERROR] Falló al leer GOOGLE_CREDENTIALS_JSON: {e}")

        # 2. Si no funcionó lo anterior, intentar cargar desde Archivo (Local)
        if not creds and settings.GOOGLE_CREDENTIALS_FILE:
            if os.path.exists(settings.GOOGLE_CREDENTIALS_FILE):
                # print(f"[INFO] Usando credenciales desde archivo: {settings.GOOGLE_CREDENTIALS_FILE}")
                creds = Credentials.from_service_account_file(settings.GOOGLE_CREDENTIALS_FILE, scopes=scopes)
            else:
                # Solo avisamos si tampoco hay JSON, para no llenar el log de ruido
                if not settings.GOOGLE_CREDENTIALS_JSON:
                    print("[WARN] No se encontró el archivo de credenciales y no hay variable JSON.")

        # 3. Autenticar cliente
        if not creds:
            raise Exception("❌ No se encontraron credenciales de Google válidas (ni archivo ni variable ENV).")

        self.client = gspread.authorize(creds)
        
        # 4. Abrir la hoja correcta
        if spreadsheet_id:
            try:
                self.sheet = self.client.open_by_key(spreadsheet_id).sheet1
            except Exception as e:
                print(f"[ERROR] No pude abrir la hoja con ID {spreadsheet_id}. Error: {e}")
                raise e
        else:
            self.sheet = self.client.open(settings.GOOGLE_SHEET_NAME).sheet1

    def load_new_leads(self) -> pd.DataFrame:
        all_records = self.sheet.get_all_records()
        df = pd.DataFrame(all_records)
        if df.empty or 'Status' not in df.columns:
            return pd.DataFrame()
        return df[df['Status'] == 'New']

    def update_lead_status(self, row_index: int, new_status: str):
        actual_row = row_index + 2
        headers = self.sheet.row_values(1)
        status_col = headers.index('Status') + 1
        self.sheet.update_cell(actual_row, status_col, new_status)

    def _normalize_phone(self, phone):
        """Deja solo los números."""
        return re.sub(r'\D', '', str(phone))

    def add_leads(self, leads_list: list) -> dict:
        """
        Agrega leads validando que el teléfono no exista ya en el Excel.
        Retorna un reporte con la cantidad de guardados y duplicados.
        """
        try:
            all_records = self.sheet.get_all_records()
            existing_df = pd.DataFrame(all_records)
            
            existing_phones = set()
            if not existing_df.empty and 'Phone' in existing_df.columns:
                existing_phones = set(self._normalize_phone(p) for p in existing_df['Phone'].astype(str))

            rows_to_add = []
            count_new = 0
            total_processed = len(leads_list)

            for lead in leads_list:
                raw_phone = lead.get('Phone', '')
                clean_phone = self._normalize_phone(raw_phone)
                
                if clean_phone in existing_phones:
                    continue
                
                row = [
                    lead.get('Nombre', ''),
                    raw_phone,   
                    "New", 
                    lead.get('Notas', '') 
                ]
                rows_to_add.append(row)
                existing_phones.add(clean_phone) 
                count_new += 1

            if rows_to_add:
                self.sheet.append_rows(rows_to_add)
                print(f"[OK] Se agregaron {count_new} leads NUEVOS.")
            
            duplicates_count = total_processed - count_new

            if count_new == 0:
                print("[AVISO] Todos los leads encontrados ya existian en el Excel.")
            
            return {
                "added": count_new,
                "duplicates": duplicates_count
            }
                
        except Exception as e:
            print(f"[ERROR] Guardando en Excel: {e}")
            return {"added": 0, "duplicates": 0}

    def update_status_by_phone(self, target_phone: str, new_status: str):
        try:
            target_clean = self._normalize_phone(target_phone)
            headers = self.sheet.row_values(1)
            try:
                if 'Phone' in headers: phone_col_index = headers.index('Phone') + 1
                elif 'phone' in headers: phone_col_index = headers.index('phone') + 1
                else: phone_col_index = 2
                status_col_index = headers.index('Status') + 1
            except ValueError:
                return False

            phone_column_values = self.sheet.col_values(phone_col_index)
            found_row = -1
            for i, val in enumerate(phone_column_values):
                val_clean = self._normalize_phone(val)
                if val_clean and target_clean.endswith(val_clean[-8:]): 
                    found_row = i + 1
                    break
            
            if found_row > 1:
                self.sheet.update_cell(found_row, status_col_index, new_status)
                return True
            else:
                return False
        except Exception as e:
            return False