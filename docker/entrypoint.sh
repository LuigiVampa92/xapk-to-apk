#!/bin/bash

if [ ! -f "xapktoapk.sign.properties" -a ! -f "xapktoapk.keystore" ]; then
    	echo "xapktoapk.sign.properties and xapktoapk.keystore not found, create a configuration with a randomly generated key."
	PASSWORD="$(LC_ALL=C tr -dc '[:alnum:]' < /dev/urandom | head -c20)"
	echo "Generated password: $PASSWORD"
    	keytool \
		-genkey \
		-v \
		-keystore xapktoapk.keystore \
		-alias xapktoapk \
		-keyalg RSA \
		-keysize 2048 \
		-validity 10000 \
		-storepass "$PASSWORD" \
		-keypass "$PASSWORD" \
		-dname "CN=xapktoapk, OU=xapktoapk, O=xapktoapk, L=xapktoapk, S=xapktoapk, C=US"
	cat <<-EOF > xapktoapk.sign.properties
		sign.enabled=true
		sign.keystore.file=/xapktoapk/xapktoapk.keystore 
		sign.keystore.password=$PASSWORD
		sign.key.alias=xapktoapk
		sign.key.password=$PASSWORD
	EOF
fi

python xapktoapk.py "$@"