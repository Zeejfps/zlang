using LexerModule;
using ParserModule.Nodes;

namespace ParserModule;

public sealed class Parser
{
    public static HashSet<TokenKind> Operators =
    [
        TokenKind.SymbolPlus
    ];

    public static AstNode Parse(IEnumerable<Token> tokens)
    {
        throw new NotImplementedException();
    }

    public static AstNode ParseExpression(TokenReader tokenReader)
    {
        //Console.WriteLine("Parsing expression");
        var left = ParseComparison(tokenReader);
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind == TokenKind.SymbolEqualsEquals ||
               nextToken.Kind == TokenKind.SymbolNotEquals)
        {
            var op = tokenReader.Read();
            //Console.WriteLine($"OP: {op}");
            var right = ParseComparison(tokenReader);
            left = new BinaryExpressionNode(left, op, right);
            nextToken = tokenReader.Peek();
        }

        return left;
    }

    public static AstNode ParseComparison(TokenReader tokenReader)
    {
        //Console.WriteLine("Parsing comparison");
        var left = ParseTerm(tokenReader);
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind == TokenKind.SymbolGreaterThan ||
               nextToken.Kind == TokenKind.SymbolLessThan ||
               nextToken.Kind == TokenKind.SymbolGreaterThanEquals ||
               nextToken.Kind == TokenKind.SymbolLessThanEquals)
        {
            var op = tokenReader.Read();
            //Console.WriteLine($"OP: {op}");
            var right = ParseTerm(tokenReader);
            left = new BinaryExpressionNode(left, op, right);
            nextToken = tokenReader.Peek();
            //Console.WriteLine($"Next token after term: {nextToken}");
        }

        return left;
    }

    public static AstNode ParseTerm(TokenReader tokenReader)
    {
        //Console.WriteLine("Parsing term");
        var left = ParseFactor(tokenReader);
        var nextToken = tokenReader.Peek();
        //Console.WriteLine($"Next token: {nextToken.Lexeme}");
        while (nextToken.Kind == TokenKind.SymbolPlus ||
               nextToken.Kind == TokenKind.SymbolMinus)
        {
            var op = tokenReader.Read();
            //Console.WriteLine($"OP: {op.Lexeme}");
            var right = ParseFactor(tokenReader);
            left = new BinaryExpressionNode(left, op, right);
            nextToken = tokenReader.Peek();
            //Console.WriteLine($"Next token after factor: {nextToken.Lexeme}");
        }

        return left;
    }

    public static AstNode ParseFactor(TokenReader tokenReader)
    {
        //Console.WriteLine("Parsing factor");
        var left = ParseUnary(tokenReader);
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind == TokenKind.SymbolStar ||
               nextToken.Kind == TokenKind.SymbolForwardSlash)
        {
            var op = tokenReader.Read();
            //Console.WriteLine($"OP: {op.Lexeme}");
            var right = ParseUnary(tokenReader);
            left = new BinaryExpressionNode(left, op, right);
            nextToken = tokenReader.Peek();
        }

        return left;
    }

    public static AstNode ParseUnary(TokenReader tokenReader)
    {
        //Console.WriteLine("Parsing unary left");
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.SymbolExclamation ||
            nextToken.Kind == TokenKind.SymbolMinus)
        {
            var op = tokenReader.Read();
            //Console.WriteLine($"OP: {op}");
            //Console.WriteLine("Parsing unary right");
            var right = ParseUnary(tokenReader);
            return new UnaryExpressionNode(op, right);
        }

        return ParsePrimaryExpression(tokenReader);
    }

    public static AstNode ParsePrimaryExpression(TokenReader tokenReader)
    {
        var token = tokenReader.Peek();
        if (token.Kind == TokenKind.LiteralInteger)
        {
            //Console.WriteLine($"Parsed integer: {token.Lexeme}");  
            tokenReader.Read();
            return new LiteralIntegerNode(token);
        }

        if (token.Kind == TokenKind.LiteralBool)
        {
            tokenReader.Read();
            return new LiteralBoolNode(token);
        }

        if (token.Kind == TokenKind.Identifier)
        {
            tokenReader.Read();
            return new IdentifierNode(token);
        }

        if (token.Kind == TokenKind.SymbolLeftParen)
        {
            tokenReader.Read();
            var expression = ParseExpression(tokenReader);
            var nextToken = tokenReader.Peek();
            if (nextToken.Kind != TokenKind.SymbolRightParen)
            {
                throw new ParserException("Expected ')'", nextToken);
            }

            tokenReader.Read();
            return expression;
        }

        throw new ParserException($"Unexpected token encountered, {token}", token);
    }

    public static AstNode ParseVarAssignmentStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordVar);
        var identifier = tokenReader.Read(TokenKind.Identifier);
        AstNode? type = null;
        if (tokenReader.Peek().Kind == TokenKind.SymbolColon)
        {
            tokenReader.Read();
            type = ParseTypeNode(tokenReader);
        }

        tokenReader.Read(TokenKind.SymbolEquals);
        var value = ParseExpression(tokenReader);
        tokenReader.Read(TokenKind.SymbolSemicolon);
        
        return new VarAssignmentStatementNode
        {
            Name = identifier.Lexeme,
            Type = type,
            Value = value,
        };
    }

    public static AstNode ParseTypeNode(TokenReader tokenReader)
    {
        var identifier = tokenReader.Read(TokenKind.Identifier);
        return new NamedTypeNode
        {
            Name = identifier.Lexeme,
        };
    }

    public static BlockStatementNode ParseBlockStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.SymbolLeftCurlyBrace);
        var statements = new List<AstNode>();

        while (tokenReader.Peek().Kind != TokenKind.SymbolRightCurlyBrace)
        {
            var statement = ParseStatement(tokenReader);
            statements.Add(statement);
        }

        tokenReader.Read();
        return new BlockStatementNode(statements);
    }

    public static AstNode ParseStatement(TokenReader tokenReader)
    {
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.KeywordVar)
        {
            return ParseVarAssignmentStatement(tokenReader);
        }

        if (nextToken.Kind == TokenKind.KeywordReturn)
        {
            return ParseReturnStatement(tokenReader);
        }
        throw new ParserException($"Unexpected token encountered, {nextToken}", nextToken);
    }

    public static AstNode ParseFunctionDeclaration(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordFunc);
        var identifier = tokenReader.Read(TokenKind.Identifier);
        var name = identifier.Lexeme;
        List<ParameterNode>? @params = null;
        
        tokenReader.Read(TokenKind.SymbolLeftParen);
        //TODO: Handle args
        if (tokenReader.Peek().Kind != TokenKind.SymbolRightParen)
        {
            @params = ParseParamsList(tokenReader);
        }
        tokenReader.Read(TokenKind.SymbolRightParen);

        AstNode? returnType = null;
        if (tokenReader.Peek().Kind == TokenKind.SymbolReturnArrow)
        {
            tokenReader.Read();
            returnType = ParseTypeNode(tokenReader);
        }

        if (@params == null)
        {
            @params = [];
        }
        
        var body = ParseBlockStatement(tokenReader);
        return new FunctionDeclarationNode
        {
            Name = name,
            Body = body,
            ReturnType = returnType,
            Parameters = @params,
        };
    }

    public static ReturnStatementNode ParseReturnStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordReturn);
        AstNode? value = null;
        if (tokenReader.Peek().Kind != TokenKind.SymbolSemicolon)
        {
            value = ParseExpression(tokenReader);
        }
        tokenReader.Read(TokenKind.SymbolSemicolon);       
        return new ReturnStatementNode
        {
            Value = value,       
        };
    }

    public static List<ParameterNode> ParseParamsList(TokenReader tokenReader)
    {
        var @params = new List<ParameterNode>();
        while (true)
        {
            var nameToken = tokenReader.Read(TokenKind.Identifier);
            var name = nameToken.Lexeme;
            tokenReader.Read(TokenKind.SymbolColon);
            var type = ParseTypeNode(tokenReader);
            @params.Add(new ParameterNode
            {
                Name = name,
                Type = type,
            });

            if (tokenReader.Peek().Kind == TokenKind.SymbolComma)
            {
                tokenReader.Read();
            }
            else
            {
                break;
            }
        }

        return @params;
    }

    public static AstNode ParseStruct(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordStruct);
        var nameToken = tokenReader.Read(TokenKind.Identifier);
        var name = nameToken.Lexeme;

        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.SymbolEquals)
        {
            tokenReader.Read();
            var qualifiedIdentifier = ParseQualifiedIdentifier(tokenReader);
            return new StructImportNode
            {
                AliasName = name,
                QualifiedIdentifier = qualifiedIdentifier,
            };
        }

        if (nextToken.Kind == TokenKind.SymbolLeftCurlyBrace)
        {
            tokenReader.Read();
            return new StructDefinitionNode
            {
                Name = name,
            };
        }
        
        throw new Exception("Expected a { or =");
    }

    public static QualifiedIdentifierNode ParseQualifiedIdentifier(TokenReader tokenReader)
    {
        var parts = new List<string>();

        parts.Add(tokenReader.Read(TokenKind.Identifier).Lexeme);
        while (tokenReader.Peek().Kind == TokenKind.SymbolDot)
        {
            tokenReader.Read();
            var identToken = tokenReader.Read(TokenKind.Identifier);
            parts.Add(identToken.Lexeme);
        }

        return new QualifiedIdentifierNode
        {
            Parts = parts
        };
    }
}