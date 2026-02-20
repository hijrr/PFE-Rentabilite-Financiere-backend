from pydantic_settings import BaseSettings,SettingsConfigDict


class Settings(BaseSettings):
      AD_SERVER: str
      AD_DOMAIN: str
      model_config = SettingsConfigDict(env_file=".env")
      
settings = Settings()

