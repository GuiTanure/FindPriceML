from __future__ import annotations

import logging
import webbrowser
from datetime import datetime, timedelta, timezone

from config import ConfigStore, ConfigurationError, parse_price
from email_sender import send_email
from ml_api import MercadoLivreAPI, MercadoLivreError
from oauth import MercadoLivreOAuth, OAuthError
from scrapper import BotBlockedError
from tracker import Tracker
from tunnel import preparar_tunnel


MERCADO_LIVRE_DEVCENTER_URL = "https://developers.mercadolivre.com.br/devcenter"
ALERT_TIMEZONE = timezone(timedelta(hours=-3), name="America/Sao_Paulo")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def print_products(store: ConfigStore) -> None:
    products = store.products()
    if not products:
        print("Nenhum produto cadastrado.")
        return
    for product in products:
        status = "ativo" if product.enabled else "inativo"
        catalog = ", ".join(product.catalog_product_ids) or "catálogos não definidos"
        print(f"{product.id} | {product.query} | {catalog} | R$ {product.target_price:.2f} | {status}")


def resolve_catalog_products(api: MercadoLivreAPI, query: str) -> list[str]:
    response = api.search_catalog_products(query, limit=20)
    results = [item for item in response.get("results", []) if item.get("id")]
    if not results:
        raise ConfigurationError("Nenhum produto de catálogo foi encontrado para essa busca.")

    catalog_ids = [item["id"] for item in results]
    print(f"Catálogos encontrados: {len(catalog_ids)}")
    for item in results:
        print(f"- {item['id']} | {item.get('name', '(sem nome)')}")
    print("Todos os catálogos acima serão armazenados automaticamente.")
    return catalog_ids


def build_tracker(store: ConfigStore) -> Tracker:
    credentials = store.credentials()
    api = MercadoLivreAPI(credentials, store.save_tokens)
    settings = store.load()["settings"]
    return Tracker(api, int(settings["search_limit"]), int(settings["max_search_pages"]), email_sender=send_email)


def authenticate(store: ConfigStore) -> None:
    tunnel_resultado = preparar_tunnel()
    # O terceiro valor identifica se o túnel foi criado nesta execução.
    # A verificação também mantém compatibilidade com implementações que
    # retornem somente (processo, redirect_uri).
    tunnel_iniciado_agora = len(tunnel_resultado) >= 3 and tunnel_resultado[2]

    if tunnel_iniciado_agora:
        print("\nAbrindo o Mercado Livre DevCenter para configurar o Redirect URI...")
        webbrowser.open(MERCADO_LIVRE_DEVCENTER_URL)
        resposta = input(
            "Você já realizou a configuração do Redirect URI no DevCenter? Digite 'sim' para continuar: "
        ).strip().lower()
        if resposta not in {"s", "sim", "y", "yes"}:
            print("Autenticação cancelada. O túnel continuará ativo.")
            return

    credentials = store.credentials()
    oauth = MercadoLivreOAuth(credentials["client_id"], credentials["client_secret"], credentials["redirect_uri"])
    tokens = oauth.authorize_local()
    store.save_tokens(
        tokens["access_token"],
        tokens["refresh_token"],
        tokens.get("expires_in"),
        tokens.get("obtained_at"),
    )
    print("Autenticação do Mercado Livre concluída.")


def _alert_window_is_open() -> bool:
    current_time = datetime.now(ALERT_TIMEZONE).time()
    return 8 <= current_time.hour < 22


def executar_busca(store: ConfigStore) -> None:
    tracker = build_tracker(store)
    products = [product for product in store.products() if product.enabled]

    if not products:
        print("Nenhum produto ativo cadastrado.")
        return

    for product in products:
        try:
            tracker.run_product(product)
        except BotBlockedError as exc:
            print(f"Alerta de parada no produto '{product.query}': {exc}")
            occurrence_time = datetime.now(ALERT_TIMEZONE).isoformat(timespec="seconds")
            alert_body = (
                "ROBÔ DO MERCADO LIVRE INTERROMPIDO\n\n"
                f"Produto:\n{product.query}\n\n"
                "Motivo:\nO tracker foi interrompido por bloqueio ou verificação do Mercado Livre.\n\n"
                f"Erro:\n{exc}\n\n"
                f"Horário:\n{occurrence_time}\n\n"
                "O tracker foi encerrado e precisa de intervenção."
            )
            if _alert_window_is_open():
                try:
                    send_email(alert_body, subject="ROBÔ PAROU")
                except Exception as alert_error:
                    print(f"Erro ao enviar alerta de parada: {alert_error}")
            else:
                print("Alerta de parada não enviado: fora do horário permitido (08:00–22:00).")
            raise


def main() -> None:
    setup_logging()
    store = ConfigStore()
    print("====================================")
    print(" Mercado Livre API MVP")
    print("====================================")
    while True:
        print("\n1 - Configurar/autenticar Mercado Livre\n2 - Adicionar produto\n3 - Listar produtos\n4 - Remover produto\n5 - Executar busca\n6 - Buscar anúncios por catalog_product_id\n7 - Sair")
        choice = input("\nEscolha: ").strip()
        try:
            if choice == "1":
                authenticate(store)
            elif choice == "2":
                query = input("Digite o produto/modelo: ").strip()
                price = parse_price(input("Digite o preço-alvo: "))
                credentials = store.credentials()
                api = MercadoLivreAPI(credentials, store.save_tokens)
                catalog_product_ids = resolve_catalog_products(api, query)
                product = store.add_product(query, price, catalog_product_ids)
                print(f"Produto salvo: {product.id}")
            elif choice == "3":
                print_products(store)
            elif choice == "4":
                product_id = input("Digite o ID do produto: ").strip()
                print("Produto removido." if store.remove_product(product_id) else "Produto não encontrado.")
            elif choice == "5":
                executar_busca(store)
            elif choice == "6":
                catalog_product_id = input("Digite o catalog_product_id (ex.: MLB22598384): ").strip()
                tracker = build_tracker(store)
                tracker.run_catalog_product(catalog_product_id)
            elif choice == "7":
                print("Saindo.")
                return
            else:
                print("Opção inválida.")
        except (ConfigurationError, MercadoLivreError, OAuthError, RuntimeError) as exc:
            print(f"ERRO: {exc}")
        except KeyboardInterrupt:
            print("\nOperação interrompida.")
            return


if __name__ == "__main__":
    main()
