from pydantic_settings import BaseSettings,SettingsConfigDict


class Settings(BaseSettings):
      AD_SERVER: str
      AD_DOMAIN: str
      BD_PASSWORD: str
      chatbot_api_key: str
      model_config = SettingsConfigDict(env_file=".env")
      dolibarr_api_key: str
      dolibarr_url: str
      
settings = Settings()

