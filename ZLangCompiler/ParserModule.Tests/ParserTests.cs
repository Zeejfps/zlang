using LexerModule;
using ParserModule.Nodes;

namespace ParserModule.Tests;

public class ParserTests
{
    [SetUp]
    public void Setup()
    {
    }

    //[Test]
    public void Test1()
    {
        const string input = "var test: u32 = 10;";
        var tokens = Lexer.Tokenize(input);
        var ast = Parser.Parse(tokens);
        var printer = new AstPrinter();
        ast.Accept(printer);
        var result = printer.ToString();
        Assert.Pass();
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
        
        astNode.AssertIsType<VarDefinitionStatementNode>(out var varAssign);
        Assert.That(varAssign.Name, Is.EqualTo("x"));
        
        varAssign.Type!.AssertIsType<NamedTypeNode>(out var namedType);
        Assert.That(namedType.Name, Is.EqualTo("u32"));
        
        varAssign.Value.AssertIsType<LiteralIntegerExpressionNode>(out var literal);
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
        Assert.That(functionDeclarationNode.Name, Is.EqualTo("main"));
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
        Assert.That(functionDeclarationNode.Name, Is.EqualTo("add"));
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
        Assert.That(functionDeclarationNode.Name, Is.EqualTo("add"));
        Assert.That(functionDeclarationNode.Body.Statements.Count, Is.EqualTo(2));
        Assert.That(functionDeclarationNode.Parameters.Count, Is.EqualTo(2));
        
        functionDeclarationNode.Body.Statements[1].AssertIsType<ReturnStatementNode>(out var returnStatementNode);
        Assert.That(returnStatementNode.Result, Is.Not.Null);
    }

    [Test]
    public void TestStructImport()
    {
        const string input = "struct MyStruct = std.some.ModuleStruct";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseStruct(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        astNode.AssertIsType<StructImportStatementNode>(out var structImportNode);
        Assert.That(structImportNode.AliasName, Is.EqualTo("MyStruct"));
        Assert.That(structImportNode.QualifiedIdentifier.Parts, 
            Is.EquivalentTo(new[] {
                "std",
                "some",
                "ModuleStruct"
            })
        );
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

        forStatementNode.Initializer.AssertIsType<VarDefinitionStatementNode>(out var initializerNode);
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
        var varDeclaration = Parser.ParseVarDeclarationStatement(tokenReader);
        
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
}