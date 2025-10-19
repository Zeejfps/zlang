using System.Text.Json.Nodes;
using LexerModule;
using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;

namespace ParserModule.Tests;

public class ParserTests
{
    [SetUp]
    public void Setup()
    {
    }
    
    [Test]
    public void TestBinaryExpression()
    {
        const string input = "10 + 5";
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        Assert.Pass();
    }
    
    [Test]
    public void TestExpression()
    {
        const string input = "10 + 5 * 10 - 29 / -30";
        Console.WriteLine(input);
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        
        Assert.Pass();
    }
    
    [Test]
    public void TestExpressionWithParanthesis()
    {
        const string input = "10 + 5 * (10 - 29) / -30";
        Console.WriteLine(input);
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        
        Assert.Pass();
    }
    
    [Test]
    public void TestExpressionWithIdentifiers()
    {
        const string input = "10 + x * (x - 29) / -y";
        Console.WriteLine(input);
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseExpression(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        
        Assert.Pass();
    }
    
    [Test]
    public void TestPrimaryExpressionNumber()
    {
        const string input = "10";
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParsePrimaryExpression(tokenReader);
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine(result);
        Assert.Pass();
    }
    
    [Test]
    public void TestVarDefinition()
    {
        const string input = "var x: u32 = 1337;";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseVarDefinitionStatement(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        astNode.AssertIsType<VarDeclarationStatementNode>(out var varAssign);
        Assert.That(varAssign.Identifier, Is.EqualTo("x"));
        
        varAssign.Type!.AssertIsType<NamedTypeNode>(out var namedType);
        Assert.That(namedType.Identifier, Is.EqualTo("u32"));
        
        varAssign.Initializer.AssertIsType<LiteralIntegerExpressionNode>(out var literal);
        Assert.That(literal.Value, Is.EqualTo(1337));
    }
    
    
    [Test]
    public void TestBlockStatement()
    {
        const string input = "{ var x: u32 = 1337; }";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseBlockStatement(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        astNode.AssertIsType<BlockStatementNode>(out var blockStatementNode);
        Assert.That(blockStatementNode.Statements.Count, Is.EqualTo(1));
    }
    
    [Test]
    public void TestVoidFunctionDeclaration()
    {
        const string input = 
@"func main() { 
    var x: u32 = 1337; 
}";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseFunctionDefinition(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        astNode.AssertIsType<FunctionDefinitionNode>(out var functionDeclarationNode);
        Assert.That(functionDeclarationNode.Signature.Identifier, Is.EqualTo("main"));
        Assert.That(functionDeclarationNode.Body.Statements.Count, Is.EqualTo(1));
    }
    
    [Test]
    public void TestFunctionDeclarationWithReturnType()
    {
        const string input = 
@"func add() -> u32 { 
    var x: u32 = 1337; 
    return x;
}";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseFunctionDefinition(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        astNode.AssertIsType<FunctionDefinitionNode>(out var functionDeclarationNode);
        Assert.That(functionDeclarationNode.Signature.Identifier, Is.EqualTo("add"));
        Assert.That(functionDeclarationNode.Body.Statements.Count, Is.EqualTo(2));
        
        functionDeclarationNode.Body.Statements[1].AssertIsType<ReturnStatementNode>(out var returnStatementNode);
        Assert.That(returnStatementNode.Result, Is.Not.Null);
    }
    
    [Test]
    public void TestFunctionDeclarationWithReturnTypeAndArguments()
    {
        const string input = 
            """
            func add(y: u32, z: u32) -> u32 { 
                var x: u32 = 1337; 
                return x;
            }
            """;
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseFunctionDefinition(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        astNode.AssertIsType<FunctionDefinitionNode>(out var functionDeclarationNode);
        Assert.That(functionDeclarationNode.Signature.Identifier, Is.EqualTo("add"));
        Assert.That(functionDeclarationNode.Body.Statements.Count, Is.EqualTo(2));
        Assert.That(functionDeclarationNode.Signature.Parameters.Count, Is.EqualTo(2));
        
        functionDeclarationNode.Body.Statements[1].AssertIsType<ReturnStatementNode>(out var returnStatementNode);
        Assert.That(returnStatementNode.Result, Is.Not.Null);
    }

    [Test]
    public void TestStructImport()
    {
        const string input = "import std.some.ModuleStruct as MyStruct;";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var importStatement = Parser.ParseImportStatement(tokenReader);
        
        var printer = new AstPrinter();
        importStatement.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        Assert.That(importStatement.AliasName, Is.EqualTo("MyStruct"));
        Assert.That(importStatement.QualifiedIdentifier.Parts, 
            Is.EquivalentTo(new[] {
                "std",
                "some",
                "ModuleStruct"
            })
        );
    }
    
    [Test]
    public void TestStructDefinition()
    {
        const string input = 
        """
        struct MyStruct {
            prop1: u32
            prop2: bool
        }"
        """;
        Console.WriteLine("Input:\n" + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var structDefinition = Parser.ParseStructDefinition(tokenReader);
        
        var printer = new AstPrinter();
        structDefinition.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(structDefinition.Name, Is.EqualTo("MyStruct"));
        Assert.That(structDefinition.Properties.Count, Is.EqualTo(2));
        Assert.That(structDefinition.Properties[0].Name, Is.EqualTo("prop1"));
        Assert.That(structDefinition.Properties[1].Name, Is.EqualTo("prop2"));
    }
    
    [Test]
    public void TestIfStatement()
    {
        const string input = 
            """
            if (x < y) {
            
            } else {
                
            }
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var ifStatementNode = Parser.ParseIfStatement(tokenReader);
        
        var printer = new AstPrinter();
        ifStatementNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);

        ifStatementNode.Condition.AssertIsType<BinaryExpressionNode>(out var condition);
        ifStatementNode.ThenBranch.AssertIsType<BlockStatementNode>(out var thenBranch);
        
        Assert.That(ifStatementNode.ElseBranch, Is.Not.Null);
        ifStatementNode.ElseBranch.AssertIsType<BlockStatementNode>(out var elseBranch);
    }
    
    [Test]
    public void TestForStatement()
    {
        const string input = 
            """
            for (var x = 0; x < 10; x++) {

            } 
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var forStatementNode = Parser.ParseForStatement(tokenReader);
        
        var printer = new AstPrinter();
        forStatementNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);

        forStatementNode.Initializer.AssertIsType<VarDeclarationStatementNode>(out var initializerNode);
        forStatementNode.Condition.AssertIsType<BinaryExpressionNode>(out var condition);
        forStatementNode.Incrementor.AssertIsType<UnaryExpressionNode>(out var incrementorNode);
        forStatementNode.Body.AssertIsType<BlockStatementNode>(out var elseBranch);
    }
    
    [Test]
    public void TestUnaryPrefixStatement()
    {
        const string input = 
            """
            ++x
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var unaryExpression = Parser.ParseUnary(tokenReader);
        
        var printer = new AstPrinter();
        unaryExpression.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
    }
    
    //[Test]
    public void TestUnaryPostfixStatement()
    {
        const string input = 
            """
            x++;
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var unaryExpression = Parser.ParseUnary(tokenReader);
        
        var printer = new AstPrinter();
        unaryExpression.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
    }
    
    [Test]
    public void TestVarDeclaration()
    {
        const string input = 
            """
            var x: u32;
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var varDeclaration = Parser.ParseVarDefinitionStatement(tokenReader);
        
        var printer = new AstPrinter();
        varDeclaration.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
    }
    
    [Test]
    public void TestVarAssignment()
    {
        const string input = 
            """
            x = 52;
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var varAssignment = Parser.ParseVarAssignmentStatement(tokenReader);
        
        var printer = new AstPrinter();
        varAssignment.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(varAssignment.Name, Is.EqualTo("x"));
        varAssignment.Value.AssertIsType<LiteralIntegerExpressionNode>(out var literal);
        Assert.That(literal.Value, Is.EqualTo(52));
    }
    
    
    [Test]
    public void TestWhileLoop()
    {
        const string input = 
            """
            while (true) {
                var i = 1;
            }
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var whileNode = Parser.ParseWhileStatement(tokenReader);
        
        var printer = new AstPrinter();
        whileNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(whileNode.Condition, Is.Not.Null);
        Assert.That(whileNode.Body, Is.Not.Null);
    }
    
    [Test]
    public void TestModuleDefinition()
    {
        const string input = 
            """
            module std.list {
                
            }
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var moduleDefinition = Parser.ParseModuleDefinition(tokenReader);
        
        var printer = new AstPrinter();
        moduleDefinition.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(moduleDefinition.Name.Parts, Is.EquivalentTo(new[] {"std", "list"}));
    }
    
    [Test]
    public void TestMetadataDefinition()
    {
        const string input = 
            """
            #metadata {
                "extern": [
                    {
                        "name": "GetSomeFunc",
                        "func": "get_some_name",
                        "lib": "kernel32.dll"
                    }
                ]
            }
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var metadata = Parser.ParseMetadata(tokenReader);
        
        Console.WriteLine("Output:\n" + metadata);
        
        Assert.That(metadata, Is.Not.Null);
    }
    
    [Test]
    public void TestGenericPtr()
    {
        const string input = 
            """
            ptr<u32>
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var ptrTypeNode = Parser.ParsePtrTypeNode(tokenReader);
        
        var printer = new AstPrinter();
        ptrTypeNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(ptrTypeNode.GenericType, Is.Not.Null);
        ptrTypeNode.GenericType.AssertIsType<NamedTypeNode>(out var namedTypeNode);
        Assert.That(namedTypeNode.Identifier, Is.EqualTo("u32"));
    }
    
    [Test]
    public void TestExternFunction()
    {
        const string input = 
            """
            extern func WriteConsoleA(
                hConsoleOutput: ptr, 
                lpBuffer: ptr<u16>, 
                nNumberOfCharsToWrite: u32,
                lpNumberOfCharsWritten: ptr<u32>,
                lpReserved: ptr
            ) -> i32;
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var externFunction = Parser.ParseExternFunctionDeclaration(tokenReader);
        
        var printer = new AstPrinter();
        externFunction.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(externFunction.Signature.Identifier, Is.EqualTo("WriteConsoleA"));
    }
    
    [Test]
    public void TestFunctionWithOneArgCall()
    {
        const string input = 
            """
            array.create(30);
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var functionCallNode = Parser.ParseFunctionCall(tokenReader);
        
        var printer = new AstPrinter();
        functionCallNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(functionCallNode.Identifier.Parts, Is.EquivalentTo(new [] {"array", "create"}));
    }
    
    [Test]
    public void TestFunctionWithMultipleArgCall()
    {
        const string input = 
            """
            array.create(30, 10, 100, 1000)
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var functionCallNode = Parser.ParseFunctionCall(tokenReader);
        
        var printer = new AstPrinter();
        functionCallNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(functionCallNode.Identifier.Parts, Is.EquivalentTo(new [] {"array", "create"}));
    }
    
    [Test]
    public void TestFunctionWithZeroArgsCall()
    {
        const string input = 
            """
            array.create()
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var functionCallNode = Parser.ParseFunctionCall(tokenReader);
        
        var printer = new AstPrinter();
        functionCallNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(functionCallNode.Identifier.Parts, Is.EquivalentTo(new [] {"array", "create"}));
    }
    
    [Test]
    public void TestFunctionWithExpressionArgsCall()
    {
        const string input = 
            """
            array.create(numbers.get_count())
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var functionCallNode = Parser.ParseFunctionCall(tokenReader);
        
        var printer = new AstPrinter();
        functionCallNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(functionCallNode.Identifier.Parts, Is.EquivalentTo(new [] {"array", "create"}));
    }
    
    [Test]
    public void TestModuleDefinitionWithMetadata()
    {
        const string input = 
            """
            module std.list {
                #metadata {
                    "extern": [
                        {
                            "name": "GetSomeName",
                            "func": "get_some_name"
                        }
                    ]
                }
            }
            """;
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var moduleDefinition = Parser.ParseModuleDefinition(tokenReader);
        
        var printer = new AstPrinter();
        moduleDefinition.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output:\n" + result);
        
        Assert.That(moduleDefinition.Name.Parts, Is.EquivalentTo(new[] {"std", "list"}));
        Assert.That(moduleDefinition.Metadata, Is.Not.Null);

        var externArray = moduleDefinition.Metadata["extern"] as JsonArray;
        Assert.That(externArray, Is.Not.Null);

        var firstElement = externArray[0]?.AsObject();
        Assert.That(firstElement, Is.Not.Null);
        
        Assert.That(firstElement["name"]?.AsValue().GetValue<string>(), Is.EqualTo("GetSomeName"));
    }
}