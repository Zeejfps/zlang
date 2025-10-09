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
    public void TestVarAssignmentStatement()
    {
        const string input = "var x: u32 = 1337;";
        Console.WriteLine("Input: " + input);
        
        var tokens = Lexer.Tokenize(input);
        using var tokenReader = new TokenReader(tokens);
        var astNode = Parser.ParseVarAssignmentStatement(tokenReader);
        
        var printer = new AstPrinter();
        astNode.Accept(printer);
        var result = printer.ToString();
        Console.WriteLine("Output: " + result);
        
        astNode.AssertIsType<VarAssignmentStatementNode>(out var varAssign);
        Assert.That(varAssign.Name, Is.EqualTo("x"));
        
        varAssign.Type!.AssertIsType<NamedTypeNode>(out var namedType);
        Assert.That(namedType.Name, Is.EqualTo("u32"));
        
        varAssign.Value.AssertIsType<LiteralIntegerNode>(out var literal);
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
        Assert.That(returnStatementNode.Value, Is.Not.Null);
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
        Assert.That(returnStatementNode.Value, Is.Not.Null);
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
}