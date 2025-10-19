using System.Text.Json.Nodes;
using LexerModule;
using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;

namespace ParserModule;

public sealed class Parser
{
    public static CompilationUnit Parse(IEnumerable<Token> tokens)
    {
        using var tokenReader = new TokenReader(tokens);
        return Parse(tokenReader);
    }
    
    public static CompilationUnit Parse(TokenReader tokenReader)
    {
        var statements = new List<TopLevelStatementNode>();
        while (tokenReader.Peek().Kind != TokenKind.EOF)
        {
            var statement = ParseTopLevelStatement(tokenReader);
            statements.Add(statement);
        }
        tokenReader.Read(TokenKind.EOF);

        return new CompilationUnit
        {
            Statements = statements,       
        };
    }

    private static TopLevelStatementNode ParseTopLevelStatement(TokenReader tokenReader)
    {
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.KeywordImport)
        {
            return ParseImportStatement(tokenReader);
        }
        
        if (nextToken.Kind == TokenKind.KeywordModule)
        {
            return ParseModuleDefinition(tokenReader);
        }
        
        throw new Exception($"Unexpected Token {nextToken}. Expected a top level statement");   
    }

    public static ModuleDefinitionNode ParseModuleDefinition(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordModule);
        var name = ParseQualifiedIdentifier(tokenReader);
        tokenReader.Read(TokenKind.SymbolLeftCurlyBrace);
        
        var body = new List<ModuleLevelStatementNode>();
        var metadata = new JsonObject();
        var nextToken = tokenReader.Peek();
        while (nextToken.Kind != TokenKind.SymbolRightCurlyBrace)
        {
            if (nextToken.Kind == TokenKind.DirectiveMetadata)
            {
                metadata.Merge(ParseMetadata(tokenReader));
            }
            else
            {
                var statement = ParseModuleLevelStatement(tokenReader);
                body.Add(statement); 
            }
            nextToken = tokenReader.Peek();       
        }
        
        tokenReader.Read(TokenKind.SymbolRightCurlyBrace);
        return new ModuleDefinitionNode
        {
            Name = name,
            Body = body.ToArray(),
            Metadata = metadata
        };
    }

    public static JsonObject ParseMetadata(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.DirectiveMetadata);
        return ParseJsonObject(tokenReader);
    }

    private static JsonObject ParseJsonObject(TokenReader tokenReader)
    {
        var jsonObject = new JsonObject();
        tokenReader.Read(TokenKind.SymbolLeftCurlyBrace);
        
        var nextToken = tokenReader.Peek();
        var keepGoing = true;
        while (keepGoing)
        {
            if (nextToken.Kind == TokenKind.EOF)
            {
                throw new Exception("Unexpected EOF while parsing json object");
            }
            
            var propName = tokenReader.Read(TokenKind.LiteralText);
            tokenReader.Read(TokenKind.SymbolColon);
            var propValue = ParseJsonValue(tokenReader);
            jsonObject.Add(propName.Lexeme, propValue);
            nextToken = tokenReader.Peek();

            if (nextToken.Kind == TokenKind.SymbolComma)
            {
                tokenReader.Read();
            }
            else
            {
                keepGoing = false;
            }
        }
        tokenReader.Read(TokenKind.SymbolRightCurlyBrace);
        return jsonObject;
    }

    private static JsonNode ParseJsonValue(TokenReader tokenReader)
    {
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.LiteralText)
        {
            var token = tokenReader.Read();
            return JsonValue.Create(token.Lexeme);
        }

        if (nextToken.Kind == TokenKind.LiteralInteger)
        {
            var token = tokenReader.Read();
            return JsonValue.Create(int.Parse(token.Lexeme));
        }
        
        if (nextToken.Kind == TokenKind.LiteralBool)
        {
            var token = tokenReader.Read();
            return JsonValue.Create(bool.Parse(token.Lexeme));
        }
        
        if (nextToken.Kind == TokenKind.SymbolLeftCurlyBrace)
        {
            return ParseJsonObject(tokenReader);
        }

        if (nextToken.Kind == TokenKind.SymbolLeftSquareBracket)
        {
            return ParseJsonArray(tokenReader);
        }
        
        throw new Exception($"Unexpected Token {nextToken}. Expected a json value");  
    }

    private static JsonArray ParseJsonArray(TokenReader tokenReader)
    {
        var array = new JsonArray();
        tokenReader.Read(TokenKind.SymbolLeftSquareBracket);
        
        var nextToken = tokenReader.Peek();
        var keepGoing = true;
        while (keepGoing)
        {
            if (nextToken.Kind == TokenKind.EOF)
            {
                throw new Exception("Unexpected EOF while parsing json array");
            }
            
            var value = ParseJsonValue(tokenReader);
            array.Add(value);
            nextToken = tokenReader.Peek();
            if (nextToken.Kind == TokenKind.SymbolComma)
            {
                tokenReader.Read();
            }
            else
            {
                keepGoing = false;
            }
        }
        
        tokenReader.Read(TokenKind.SymbolRightSquareBracket);
        return array;
    }

    private static ModuleLevelStatementNode ParseModuleLevelStatement(TokenReader tokenReader)
    {
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.KeywordFunc)
        {
            return ParseFunctionDefinition(tokenReader);
        }

        if (nextToken.Kind == TokenKind.KeywordExtern)
        {
            return ParseExternFunctionDeclaration(tokenReader);
        }

        throw new Exception($"Unexpected Token {nextToken}. Expected a module level statement");
    }

    public static ExpressionNode ParseExpression(TokenReader tokenReader)
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

    public static ExpressionNode ParseComparison(TokenReader tokenReader)
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

    public static ExpressionNode ParseTerm(TokenReader tokenReader)
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

    public static ExpressionNode ParseFactor(TokenReader tokenReader)
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

    public static ExpressionNode ParseUnary(TokenReader tokenReader)
    {
        //Console.WriteLine("Parsing unary left");
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.SymbolExclamation ||
            nextToken.Kind == TokenKind.SymbolMinus ||
            nextToken.Kind == TokenKind.SymbolPlusPlus || 
            nextToken.Kind == TokenKind.SymbolMinsMinus)
        {
            var op = tokenReader.Read();
            //Console.WriteLine($"OP: {op}");
            //Console.WriteLine("Parsing unary right");
            var right = ParseUnary(tokenReader);
            return new UnaryExpressionNode
            {
                Operator = op,
                Value = right,       
                IsPrefix = true
            };
        }

        var left = ParsePrimaryExpression(tokenReader);
        nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.SymbolPlusPlus ||
            nextToken.Kind == TokenKind.SymbolMinsMinus)
        {
            var op = tokenReader.Read();
            return new UnaryExpressionNode
            {
                Operator = op,
                Value = left
            };       
        }

        return left;
    }

    public static ExpressionNode ParsePrimaryExpression(TokenReader tokenReader)
    {
        var token = tokenReader.Peek();
        if (token.Kind == TokenKind.LiteralInteger)
        {
            //Console.WriteLine($"Parsed integer: {token.Lexeme}");  
            tokenReader.Read();
            return new LiteralIntegerExpressionNode(token);
        }

        if (token.Kind == TokenKind.LiteralBool)
        {
            tokenReader.Read();
            return new LiteralBoolExpressionNode(token);
        }

        if (token.Kind == TokenKind.Identifier)
        {
            var identifier = ParseQualifiedIdentifier(tokenReader);
            if (tokenReader.Peek().Kind == TokenKind.SymbolLeftParen)
            {
                var args = ParseFunctionArgs(tokenReader);
                return new FunctionCallNode
                {
                    Identifier = identifier,
                    Arguments = args
                };
            }
            
            return identifier;
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

    public static VarDefinitionStatementNode ParseVarDefinitionStatement(TokenReader tokenReader)
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
        
        return new VarDefinitionStatementNode
        {
            Name = identifier.Lexeme,
            Type = type,
            Value = value,
        };
    }
    
    public static VarDeclarationStatementNode ParseVarDeclarationStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordVar);
        var identifier = tokenReader.Read(TokenKind.Identifier);
        AstNode? type = null;
        if (tokenReader.Peek().Kind == TokenKind.SymbolColon)
        {
            tokenReader.Read();
            type = ParseTypeNode(tokenReader);
        }
        
        tokenReader.Read(TokenKind.SymbolSemicolon);
        
        return new VarDeclarationStatementNode
        {
            Name = identifier.Lexeme,
            Type = type,
        };
    }
    
    public static VarAssignmentStatementNode ParseVarAssignmentStatement(TokenReader tokenReader)
    {
        var identifier = tokenReader.Read(TokenKind.Identifier);

        tokenReader.Read(TokenKind.SymbolEquals);
        var value = ParseExpression(tokenReader);
        tokenReader.Read(TokenKind.SymbolSemicolon);
        
        return new VarAssignmentStatementNode
        {
            Name = identifier.Lexeme,
            Value = value,
        };
    }
    
    public static WhileStatementNode ParseWhileStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordWhile);
        tokenReader.Read(TokenKind.SymbolLeftParen);
        var condition = ParseExpression(tokenReader);
        tokenReader.Read(TokenKind.SymbolRightParen);
        var body = ParseStatement(tokenReader);
        
        return new WhileStatementNode
        {
            Condition = condition,
            Body = body,
        };
    }

    public static TypeNode ParseTypeNode(TokenReader tokenReader)
    {
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.TypePtr)
        {
            return ParsePtrTypeNode(tokenReader);
        }
        
        var identifier = tokenReader.Read(TokenKind.Identifier);
        return new NamedTypeNode
        {
            Identifier = identifier.Lexeme,
        };
    }

    public static PtrTypeNode ParsePtrTypeNode(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.TypePtr);
        TypeNode? genericType = null;
        if (tokenReader.Peek().Kind == TokenKind.SymbolLessThan)
        {
            tokenReader.Read(TokenKind.SymbolLessThan);
            genericType = ParseTypeNode(tokenReader);
            tokenReader.Read(TokenKind.SymbolGreaterThan);
        }

        return new PtrTypeNode
        {
            GenericType = genericType,
        };
    }
    
    public static BlockStatementNode ParseBlockStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.SymbolLeftCurlyBrace);
        var statements = new List<StatementNode>();

        while (tokenReader.Peek().Kind != TokenKind.SymbolRightCurlyBrace)
        {
            var statement = ParseStatement(tokenReader);
            statements.Add(statement);
        }

        tokenReader.Read();
        return new BlockStatementNode(statements);
    }

    public static StatementNode ParseStatement(TokenReader tokenReader)
    {
        var nextToken = tokenReader.Peek();
        if (nextToken.Kind == TokenKind.KeywordIf)
        {
            return ParseIfStatement(tokenReader);
        }

        if (nextToken.Kind == TokenKind.KeywordElse)
        {
            return ParseStatement(tokenReader);
        }
        
        if (nextToken.Kind == TokenKind.SymbolLeftCurlyBrace)
        {
            return ParseBlockStatement(tokenReader);
        }
        
        if (nextToken.Kind == TokenKind.KeywordVar)
        {
            return ParseVarDefinitionStatement(tokenReader);
        }

        if (nextToken.Kind == TokenKind.KeywordReturn)
        {
            return ParseReturnStatement(tokenReader);
        }

        if (nextToken.Kind == TokenKind.Identifier)
        {
            var identifier = ParseQualifiedIdentifier(tokenReader);
            if (tokenReader.Peek().Kind == TokenKind.SymbolLeftParen)
            {
                var args = ParseFunctionArgs(tokenReader);
                tokenReader.Read(TokenKind.SymbolSemicolon);
                return new ExpressionStatement
                {
                    Expression = new FunctionCallNode
                    {
                        Identifier = identifier,
                        Arguments = args
                    }
                };
            }
           
            tokenReader.Read(TokenKind.SymbolEquals);
            var value = ParseExpression(tokenReader);
            tokenReader.Read(TokenKind.SymbolSemicolon);
        
            return new VarAssignmentStatementNode
            {
                Name = identifier.ToString(),
                Value = value,
            };
        }
        
        throw new ParserException($"Unexpected token encountered, {nextToken}", nextToken);
    }

    public static FunctionDefinitionNode ParseFunctionDefinition(TokenReader tokenReader)
    {
        var signature = ParseFunctionSignature(tokenReader);
        var body = ParseBlockStatement(tokenReader);
        return new FunctionDefinitionNode
        {
            Signature = signature,
            Body = body
        };
    }

    public static ReturnStatementNode ParseReturnStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordReturn);
        ExpressionNode? value = null;
        if (tokenReader.Peek().Kind != TokenKind.SymbolSemicolon)
        {
            value = ParseExpression(tokenReader);
        }
        tokenReader.Read(TokenKind.SymbolSemicolon);       
        return new ReturnStatementNode
        {
            Result = value,       
        };
    }

    public static List<FunctionParameter> ParseParamsList(TokenReader tokenReader)
    {
        var @params = new List<FunctionParameter>();
        while (true)
        {
            var nameToken = tokenReader.Read(TokenKind.Identifier);
            var name = nameToken.Lexeme;
            tokenReader.Read(TokenKind.SymbolColon);
            var type = ParseTypeNode(tokenReader);
            @params.Add(new FunctionParameter
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

    public static ImportStatementNode ParseImportStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordImport);
        var qualifiedIdentifier = ParseQualifiedIdentifier(tokenReader);
        tokenReader.Read(TokenKind.KeywordAs);
        var nameToken = tokenReader.Read(TokenKind.Identifier);
        var name = nameToken.Lexeme;
        tokenReader.Read(TokenKind.SymbolSemicolon);
        
        return new ImportStatementNode
        {
            AliasName = name,
            QualifiedIdentifier = qualifiedIdentifier,
        };
    }
    
    public static StructDefinitionNode ParseStructDefinition(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordStruct);
        var nameToken = tokenReader.Read(TokenKind.Identifier);
        var name = nameToken.Lexeme;
        tokenReader.Read(TokenKind.SymbolLeftCurlyBrace);

        var props = new List<StructFieldDeclarationNode>();
        while (tokenReader.Peek().Kind != TokenKind.SymbolRightCurlyBrace)
        {
            var prop = ParseStructPropertyDeclaration(tokenReader);
            props.Add(prop);
        }
        
        tokenReader.Read(TokenKind.SymbolRightCurlyBrace);
        return new StructDefinitionNode
        {
            Name = name,
            Properties = props,
        };
    }

    public static StructFieldDeclarationNode ParseStructPropertyDeclaration(TokenReader tokenReader)
    {
        var propName = tokenReader.Read(TokenKind.Identifier);
        tokenReader.Read(TokenKind.SymbolColon);
        var propType = ParseTypeNode(tokenReader);
        return new StructFieldDeclarationNode
        {
            Name = propName.Lexeme,
            Type = propType,
        };
    }

    public static QualifiedIdentifierExpressionNode ParseQualifiedIdentifier(TokenReader tokenReader)
    {
        var parts = new List<string>();

        parts.Add(tokenReader.Read(TokenKind.Identifier).Lexeme);
        while (tokenReader.Peek().Kind == TokenKind.SymbolDot)
        {
            tokenReader.Read();
            var identToken = tokenReader.Read(TokenKind.Identifier);
            parts.Add(identToken.Lexeme);
        }

        return new QualifiedIdentifierExpressionNode
        {
            Parts = parts
        };
    }

    public static IfStatementNode ParseIfStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordIf);

        var condition = ParseExpression(tokenReader);
        var thenBranch = ParseStatement(tokenReader);
        StatementNode? elseBranch = null;
        if (tokenReader.Peek().Kind == TokenKind.KeywordElse)
        {
            tokenReader.Read(); 
            elseBranch = ParseStatement(tokenReader);
        }
        
        return new IfStatementNode
        {
            Condition = condition,
            ThenBranch = thenBranch,
            ElseBranch = elseBranch
        };
    }

    public static ForStatemetNode ParseForStatement(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordFor);
        tokenReader.Read(TokenKind.SymbolLeftParen);
        var initializer = ParseStatement(tokenReader);
        
        var condition = ParseExpression(tokenReader);
        tokenReader.Read(TokenKind.SymbolSemicolon);
        
        var incrementor = ParseExpression(tokenReader);
        tokenReader.Read(TokenKind.SymbolRightParen);
        
        var body = ParseStatement(tokenReader);
        
        return new ForStatemetNode
        {
            Initializer = initializer,
            Condition = condition,
            Incrementor = incrementor,
            Body = body,       
        };
    }

    public static ExternFunctionDeclarationNode ParseExternFunctionDeclaration(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordExtern);
        var signature = ParseFunctionSignature(tokenReader);
        tokenReader.Read(TokenKind.SymbolSemicolon);
        return new ExternFunctionDeclarationNode
        {
            Signature = signature
        };
    }

    public static FunctionSignature ParseFunctionSignature(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.KeywordFunc);
        var identifier = tokenReader.Read(TokenKind.Identifier);
        var name = identifier.Lexeme;
        List<FunctionParameter>? @params = null;
        
        tokenReader.Read(TokenKind.SymbolLeftParen);
        //TODO: Handle args
        if (tokenReader.Peek().Kind != TokenKind.SymbolRightParen)
        {
            @params = ParseParamsList(tokenReader);
        }
        tokenReader.Read(TokenKind.SymbolRightParen);

        TypeNode? returnType = null;
        if (tokenReader.Peek().Kind == TokenKind.SymbolReturnArrow)
        {
            tokenReader.Read();
            returnType = ParseTypeNode(tokenReader);
        }

        return new FunctionSignature
        {
            Identifier = name,
            Parameters = @params ?? [],
            ReturnType = returnType
        };
    }

    public static FunctionCallNode ParseFunctionCall(TokenReader tokenReader)
    {
        var identifier = ParseQualifiedIdentifier(tokenReader);
        var args = ParseFunctionArgs(tokenReader);
        return new FunctionCallNode
        {
            Identifier = identifier,
            Arguments = args
        };
    }

    private static List<ExpressionNode> ParseFunctionArgs(TokenReader tokenReader)
    {
        tokenReader.Read(TokenKind.SymbolLeftParen);
        var args = new List<ExpressionNode>();

        var keepGoing = tokenReader.Peek().Kind != TokenKind.SymbolRightParen;
        while (keepGoing)
        {
            var arg = ParseExpression(tokenReader);
            args.Add(arg);
            
            keepGoing = tokenReader.Peek().Kind == TokenKind.SymbolComma;
            if (keepGoing)
            {
                tokenReader.Read(TokenKind.SymbolComma);
            }
        }
        tokenReader.Read(TokenKind.SymbolRightParen);
        
        return args;
    } 
}