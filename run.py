# run.py
import os
from app import app

if __name__ == '__main__':
    # Obtém a porta da variável de ambiente, com um padrão para desenvolvimento local
    port = int(os.environ.get("PORT", 5001))
    
    # Executa a aplicação
    # O host '0.0.0.0' é importante para a implantação em serviços como o Railway
    # debug=True é útil para desenvolvimento, mas deve ser False em produção
    app.run(host='0.0.0.0', port=port, debug=True)
